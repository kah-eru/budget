import json
from datetime import date
from decimal import Decimal
from unittest import mock

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from budget import plaid as bank
from budget.models import (
    Account, AccountShare, BankConnection, Budget, BudgetAlert, Category, Membership, Rule, SplitLine, Transaction, TransactionAnnotation, Workspace,
)

KEYS = {"PLAID_CLIENT_ID": "synthetic-client", "PLAID_SECRET": "synthetic-secret", "PLAID_TOKEN_KEY": Fernet.generate_key().decode()}
DAY = date(2026, 5, 10)


def txn(id, amount, account="acc-1", name="Cafe", pending=False, pending_id=None, category="FOOD_AND_DRINK_COFFEE", currency="USD", day=DAY):
    return {"id": id, "account": account, "amount": Decimal(amount), "currency": currency, "date": day, "name": name,
            "pending": pending, "pending_id": pending_id, "category": category}


def page(added=(), modified=(), removed=(), cursor="c1", more=False, status="HISTORICAL_UPDATE_COMPLETE"):
    return {"added": list(added), "modified": list(modified), "removed": list(removed), "next_cursor": cursor, "has_more": more, "status": status}


@override_settings(**KEYS)
class PlaidTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)

    def setUp(self):
        with override_settings(**KEYS):
            self.connection = BankConnection.objects.create(owner=self.alice, item_id="item-1", access_token=bank.encrypt("access-sandbox-1"),
                                                            institution_name="First Platypus Bank")
        self.checking = Account.objects.create(owner=self.alice, name="Plaid Checking", connection=self.connection, provider_account_id="acc-1", mask="0000")
        AccountShare.objects.create(account=self.checking, workspace=self.group)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")

    def sync(self, *pages):
        BankConnection.objects.filter(pk=self.connection.pk).update(sync_started_at=None)  # past the cooldown
        with mock.patch("budget.plaid._page", side_effect=list(pages)) as fetched:
            result = bank.sync(BankConnection.objects.get(pk=self.connection.pk))
        return result, fetched

    def test_access_token_is_encrypted_at_rest_and_exchange_is_validated(self):
        with mock.patch("budget.plaid.exchange", return_value=("access-sandbox-2", "item-2")):
            response = self.client.post("/banks/exchange/", json.dumps({"public_token": "public-sandbox-2", "institution": "Tartan Bank"}),
                                        content_type="application/json")
            self.assertEqual(response.status_code, 200)
            stored = BankConnection.objects.get(item_id="item-2")
            self.assertEqual(response.json()["next"], f"/banks/{stored.pk}/accounts/")
            self.assertNotIn("access-sandbox-2", stored.access_token)
            self.assertEqual(bank.decrypt(stored.access_token), "access-sandbox-2")
            self.assertEqual(self.client.post("/banks/exchange/", json.dumps({"public_token": "evil"}), content_type="application/json").status_code, 400)
        with override_settings(PLAID_SECRET=""):
            self.assertEqual(self.client.get("/banks/connect/").status_code, 404)

    def test_only_the_owner_reaches_a_connection(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        base = f"/banks/{self.connection.pk}/"
        self.assertEqual(self.client.get(base + "accounts/").status_code, 404)
        for action in ("accounts/", "sync/", "disconnect/"):
            self.assertEqual(self.client.post(base + action).status_code, 404)
        self.assertTrue(BankConnection.objects.filter(pk=self.connection.pk).exists())

    @mock.patch("budget.plaid.accounts", return_value={"institution_id": "ins_109508", "accounts": [
        {"id": "acc-1", "name": "Plaid Checking", "mask": "0000", "type": "depository", "subtype": "checking"},
        {"id": "acc-2", "name": "Plaid Credit Card", "mask": "3333", "type": "credit", "subtype": "credit card"}]})
    def test_chooser_imports_only_ticked_accounts_privately_and_resyncs(self, _):
        self.sync(page(added=[txn("t1", "4.50")]))
        response = self.client.get(f"/banks/{self.connection.pk}/accounts/")
        self.assertContains(response, "Plaid Credit Card")
        self.assertContains(response, "Already imported")
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50"), txn("t2", "25.00", account="acc-2")], cursor="c2")]) as fetched:
            self.client.post(f"/banks/{self.connection.pk}/accounts/", {"accounts": ["acc-2"]})
        card = Account.objects.get(provider_account_id="acc-2")
        self.assertEqual((card.owner, card.connection, card.mask), (self.alice, self.connection, "3333"))
        self.assertFalse(card.shares.exists())
        self.assertEqual(fetched.call_args.args[1], "")  # a newly imported account needs history the cursor has passed
        self.assertEqual(Transaction.objects.filter(provider_id="t1").count(), 1)
        self.assertTrue(Transaction.objects.filter(account=card, provider_id="t2").exists())

    def test_added_modified_removed_and_what_is_skipped(self):
        self.sync(page(added=[txn("t1", "4.50"), txn("t2", "9.00", account="acc-9"), txn("t3", "3.00", currency="EUR"), txn("t4", "0.00")]))
        self.assertEqual(list(Transaction.objects.values_list("provider_id", "amount_cents")), [("t1", 450)])
        self.sync(page(added=[txn("t1", "4.50")], modified=[txn("t1", "5.25", name="Cafe Uno")], cursor="c2"))
        row = Transaction.objects.get()
        self.assertEqual((row.amount_cents, row.description, row.classification), (525, "Cafe Uno", "expense"))
        self.sync(page(removed=["t1"], cursor="c3"))
        self.assertFalse(Transaction.objects.exists())
        self.assertEqual(BankConnection.objects.get(pk=self.connection.pk).cursor, "c3")

    def test_pending_to_posted_keeps_workspace_edits_and_counts_once(self):
        self.sync(page(added=[txn("p1", "12.00", pending=True)]))
        pending = Transaction.objects.get()
        dining, travel = (Category.objects.get(workspace=self.group, name=n) for n in ("Dining", "Travel"))
        TransactionAnnotation.objects.update_or_create(transaction=pending, workspace=self.group, defaults={"display_name": "Lunch with Sam", "category": dining, "category_source": "manual"})
        SplitLine.objects.create(transaction=pending, workspace=self.group, category=travel, amount_cents=1200)
        self.sync(page(added=[txn("t1", "12.00", pending_id="p1")], removed=["p1"], cursor="c2"))
        row = Transaction.objects.get()
        self.assertEqual((row.pk, row.provider_id, row.pending), (pending.pk, "t1", False))
        self.assertEqual(row.annotations.get(workspace=self.group).display_name, "Lunch with Sam")
        self.assertTrue(row.split_lines.exists())

    def test_a_posted_amount_that_differs_rescales_a_hand_split(self):
        self.sync(page(added=[txn("p1", "50.00", pending=True)]))
        pending = Transaction.objects.get()
        dining, travel = (Category.objects.get(workspace=self.group, name=n) for n in ("Dining", "Travel"))
        SplitLine.objects.create(transaction=pending, workspace=self.group, category=dining, amount_cents=3000)
        SplitLine.objects.create(transaction=pending, workspace=self.group, category=travel, amount_cents=2000)
        self.sync(page(added=[txn("t1", "60.00", pending_id="p1")], removed=["p1"], cursor="c2"))  # a tip was added
        self.assertEqual(dict(SplitLine.objects.values_list("category__name", "amount_cents")), {"Dining": 3600, "Travel": 2400})

    def test_a_failure_on_page_two_changes_nothing(self):
        (status, _), _ = self.sync(page(added=[txn("t1", "4.50")], more=True), bank.PlaidError("INTERNAL_SERVER_ERROR"))
        self.assertEqual(status, "error")
        self.assertFalse(Transaction.objects.exists())
        connection = BankConnection.objects.get(pk=self.connection.pk)
        self.assertEqual((connection.cursor, connection.status, connection.error_code), ("", "error", "INTERNAL_SERVER_ERROR"))

    def test_mutation_during_pagination_restarts_from_the_committed_cursor(self):
        _, fetched = self.sync(page(added=[txn("t1", "4.50")], more=True), bank.PlaidError("TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"),
                               page(added=[txn("t1", "4.50"), txn("t2", "6.00")], cursor="c2"))
        self.assertEqual([c.args[1] for c in fetched.call_args_list], ["", "c1", ""])
        self.assertEqual(Transaction.objects.count(), 2)

    def test_sync_now_cooldown_and_a_concurrent_commit(self):
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]) as fetched:
            self.client.post(f"/banks/{self.connection.pk}/sync/")
            response = self.client.post(f"/banks/{self.connection.pk}/sync/", follow=True)
        self.assertEqual(fetched.call_count, 1)
        self.assertContains(response, "less than a minute ago")

        def other_sync_commits(token, cursor):
            BankConnection.objects.filter(pk=self.connection.pk).update(cursor="other")
            return page(added=[txn("t9", "1.00")], cursor="c9")
        BankConnection.objects.filter(pk=self.connection.pk).update(sync_started_at=None)
        with mock.patch("budget.plaid._page", side_effect=other_sync_commits):
            self.assertEqual(bank.sync(BankConnection.objects.get(pk=self.connection.pk))[0], "busy")
        self.assertFalse(Transaction.objects.filter(provider_id="t9").exists())

    def test_bank_types_count_but_only_rules_or_hand_choices_set_categories(self):
        Rule.objects.create(workspace=self.personal, pattern="corner", category=Category.objects.get(workspace=self.personal, name="Shopping"))
        self.sync(page(added=[
            txn("pay", "-500.00", name="Card payment", category="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
            txn("move", "-50.00", name="From savings", category="TRANSFER_IN_ACCOUNT_TRANSFER"),
            txn("wage", "-1000.00", name="Payroll", category="INCOME_WAGES"),
            txn("back", "-20.00", name="Store return", category="GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE"),
            txn("food", "40.00", name="Grocer", category="FOOD_AND_DRINK_GROCERIES"),
            txn("cafe", "4.50", name="Corner cafe", category="FOOD_AND_DRINK_COFFEE")]))
        kinds = dict(Transaction.objects.values_list("provider_id", "classification"))
        self.assertEqual(kinds, {"pay": "transfer", "move": "transfer", "wage": "income", "back": "refund", "food": "expense", "cafe": "expense"})
        category = lambda pid, ws: getattr(TransactionAnnotation.objects.filter(transaction__provider_id=pid, workspace=ws).first(), "category", None)
        # The bank's own category guess is ignored: imports start uncategorized until a rule or a person sorts them.
        self.assertEqual((category("food", self.group), category("cafe", self.group), category("cafe", self.personal).name), (None, None, "Shopping"))
        TransactionAnnotation.objects.create(transaction=Transaction.objects.get(provider_id="food"), workspace=self.group,
                                             category=Category.objects.get(workspace=self.group, name="Health"), category_source="manual")
        self.sync(page(modified=[txn("food", "41.00", name="Grocer", category="FOOD_AND_DRINK_GROCERIES")], cursor="c2"))
        self.assertEqual(category("food", self.group).name, "Health")

    @mock.patch("django.utils.timezone.localdate", return_value=DAY)
    def test_a_sync_that_crosses_a_budget_alerts(self, _):
        dining = Category.objects.get(workspace=self.group, name="Dining")
        Rule.objects.create(workspace=self.group, pattern="cafe", category=dining)
        Budget.objects.create(workspace=self.group, category=dining, limit_cents=100)
        with self.captureOnCommitCallbacks(execute=True):
            self.sync(page(added=[txn("t1", "4.50")]))
        self.assertTrue(BudgetAlert.objects.filter(recipient=self.bob, silent=False).exists())

    def test_synced_rows_are_read_only(self):
        self.sync(page(added=[txn("t1", "4.50")]))
        row = Transaction.objects.get()
        url = f"/workspaces/{self.personal.pk}/accounts/{self.checking.pk}/transactions/{row.pk}/"
        response = self.client.post(url, {"posted_on": "2020-01-01", "amount": "999.00", "description": "X", "classification": "transfer"})
        self.assertRedirects(response, url + "annotate/", fetch_redirect_response=False)  # the type is set per workspace there
        row.refresh_from_db()
        self.assertEqual((row.amount_cents, row.classification), (450, "expense"))

    def test_disconnect_keeps_the_connection_until_plaid_confirms(self):
        self.sync(page(added=[txn("t1", "4.50")]))
        with mock.patch("budget.plaid.remove", side_effect=bank.PlaidError("INTERNAL_SERVER_ERROR")):
            response = self.client.post(f"/banks/{self.connection.pk}/disconnect/", follow=True)
        self.assertContains(response, "reach Plaid to disconnect")
        self.assertTrue(BankConnection.objects.exists())  # the token stays, so a retry can still revoke it
        with mock.patch("budget.plaid.remove", side_effect=bank.PlaidError("ITEM_NOT_FOUND")):  # already gone at Plaid
            self.assertEqual(self.client.post(f"/banks/{self.connection.pk}/disconnect/").status_code, 302)
        self.assertFalse(BankConnection.objects.exists())
        self.checking.refresh_from_db()
        self.assertIsNone(self.checking.connection)
        self.assertEqual(Transaction.objects.count(), 1)
