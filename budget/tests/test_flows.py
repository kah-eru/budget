import importlib
from datetime import date
from decimal import Decimal
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from budget import flows, imports, plaid
from budget.models import Account, AccountShare, ImportBatch, Membership, Transaction, TransactionAnnotation, Workspace
from budget.reporting import visible_transactions

SEP = date(2026, 9, 1)


def day(n):
    return date(2026, 9, n)


class PairTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.checking, cls.savings, cls.card = [Account.objects.create(owner=cls.alice, name=n) for n in ("Checking", "Savings", "Card")]

    def t(self, account, cents, n, money_in, classification="transfer"):
        return Transaction.objects.create(account=account, amount_cents=cents, posted_on=day(n), money_in=money_in, classification=classification)

    def pairs(self):
        return flows.pair(visible_transactions(self.alice, self.personal))

    def test_pairs_one_for_one_closest_date_first(self):
        out = self.t(self.checking, 50000, 10, False)
        near, far = self.t(self.savings, 50000, 11, True), self.t(self.card, 50000, 14, True)
        second = self.t(self.checking, 50000, 15, False)
        self.assertEqual(self.pairs(), {out.pk: near.pk, second.pk: far.pk})

    def test_needs_same_amount_other_account_within_five_days_and_a_transfer(self):
        out = self.t(self.checking, 50000, 10, False)
        self.t(self.savings, 50001, 10, True)       # different amount
        self.t(self.checking, 50000, 11, True)      # same account
        self.t(self.savings, 50000, 16, True)       # six days later
        self.t(self.savings, 50000, 12, True, "income")  # not a transfer
        self.assertEqual(self.pairs(), {})
        annotated = self.t(self.savings, 50000, 15, True, "income")
        TransactionAnnotation.objects.create(transaction=annotated, workspace=self.personal, classification="transfer")
        self.assertEqual(self.pairs(), {out.pk: annotated.pk})  # the workspace's type counts


class DirectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.account = Account.objects.create(owner=cls.alice, name="Checking")

    def test_plaid_sign_sets_direction(self):
        base = {"id": "x", "account": "a", "currency": "USD", "date": SEP, "name": "Move", "pending": False, "pending_id": None, "category": "TRANSFER_OUT_ACCOUNT_TRANSFER"}
        self.assertFalse(plaid._fields({**base, "amount": Decimal("25.00")})["money_in"])
        self.assertTrue(plaid._fields({**base, "amount": Decimal("-25.00"), "category": "TRANSFER_IN_DEPOSIT"})["money_in"])
        self.assertIn("money_in", plaid.UPDATED)

    def test_csv_sign_sets_direction(self):
        text = "Date,Description,Amount\n09/01/2026,COFFEE,-4.50\n09/02/2026,FROM SAVINGS,100.00\n"
        mapping = {"header": True, "date_col": 0, "description_col": 1, "amount_col": 2, "credit_col": None, "sign": "negative", "incoming": "transfer", "category_col": None}
        parsed, errors, _ = imports.parse(imports.rows(text), mapping)
        batch = ImportBatch.objects.create(account=self.account, file_name="a.csv", sha256="0" * 64, content=text)
        imports.commit(batch, parsed, [], self.personal)
        self.assertEqual(sorted(Transaction.objects.values_list("description", "money_in")), [("COFFEE", False), ("FROM SAVINGS", True)])

    def test_manual_form_offers_transfer_in_and_out(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.personal.pk}/accounts/{self.account.pk}/transactions/new/"
        for kind, money_in in (("transfer_in", True), ("transfer", False), ("income", True), ("expense", False)):
            self.client.post(url, {"posted_on": "2026-09-01", "amount": "10.00", "classification": kind, "description": kind})
            row = Transaction.objects.get(description=kind)
            self.assertEqual((row.classification, row.money_in), ("transfer" if kind.startswith("transfer") else kind, money_in))
        edit = self.client.get(f"/workspaces/{self.personal.pk}/accounts/{self.account.pk}/transactions/{Transaction.objects.get(description='transfer_in').pk}/")
        self.assertContains(edit, '<option value="transfer_in" selected>')

    def test_backfill_guesses_existing_rows(self):
        card = Account.objects.create(owner=self.alice, name="Card", balance_kind="liability")
        batch = ImportBatch.objects.create(account=self.account, file_name="b.csv", sha256="1" * 64, status="done")
        rows = {
            "refund": Transaction.objects.create(account=self.account, amount_cents=1, posted_on=SEP, classification="refund"),
            "expense": Transaction.objects.create(account=self.account, amount_cents=1, posted_on=SEP),
            "in": Transaction.objects.create(account=self.account, amount_cents=1, posted_on=SEP, classification="transfer", provider_id="p1", provider_category="TRANSFER_IN_DEPOSIT"),
            "csv": Transaction.objects.create(account=self.account, amount_cents=1, posted_on=SEP, classification="transfer", import_batch=batch, source_row=1),
            "card": Transaction.objects.create(account=card, amount_cents=1, posted_on=SEP, classification="transfer", provider_id="p2", provider_category="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
            "out": Transaction.objects.create(account=self.account, amount_cents=1, posted_on=SEP, classification="transfer", provider_id="p3", provider_category="LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"),
        }
        Transaction.objects.update(money_in=False)
        importlib.import_module("budget.migrations.0021_money_in").backfill(apps, None)
        got = {k: Transaction.objects.get(pk=r.pk).money_in for k, r in rows.items()}
        self.assertEqual(got, {"refund": True, "expense": False, "in": True, "csv": True, "card": True, "out": False})


class LanesPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        # Synced names carry their mask, as bank_accounts saves them.
        cls.checking = Account.objects.create(owner=cls.alice, name="Checking ••0000", mask="0000")
        cls.savings = Account.objects.create(owner=cls.alice, name="Savings ••1111", mask="1111")
        cls.hidden = Account.objects.create(owner=cls.alice, name="Secret stash")
        AccountShare.objects.create(account=cls.checking, workspace=cls.group)
        AccountShare.objects.create(account=cls.savings, workspace=cls.group)
        make = Transaction.objects.create
        cls.out = make(account=cls.checking, amount_cents=50000, posted_on=day(10), classification="transfer", description="To savings")
        cls.into = make(account=cls.savings, amount_cents=50000, posted_on=day(11), classification="transfer", money_in=True, description="From checking")
        cls.stash = make(account=cls.checking, amount_cents=7000, posted_on=day(12), classification="transfer", description="To stash")
        make(account=cls.hidden, amount_cents=7000, posted_on=day(12), classification="transfer", money_in=True, description="Stash in")
        make(account=cls.checking, amount_cents=1200, posted_on=day(12), description="Coffee")

    def get(self, user, workspace, **params):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        return self.client.get(f"/workspaces/{workspace.pk}/transactions/", {"start": "2026-09-01", "end": "2026-09-30", **params})

    def test_ticked_accounts_filter_the_list_totals_and_export(self):
        response = self.get(self.alice, self.personal, account=[self.savings.pk, self.hidden.pk])
        self.assertContains(response, "From checking")
        self.assertNotContains(response, "Coffee")
        self.assertEqual(response.context["totals"]["posted_cents"], 0)
        everything = self.get(self.alice, self.personal)
        self.assertEqual(everything.context["totals"]["posted_cents"], 1200)
        export = self.client.get(f"/workspaces/{self.personal.pk}/transactions/export.csv", {"start": "2026-09-01", "end": "2026-09-30", "account": [self.checking.pk]})
        self.assertIn(b"Coffee", export.content)
        self.assertNotIn(b"From checking", export.content)

    def test_side_by_side_draws_pairs_and_never_names_a_private_account(self):
        response = self.get(self.bob, self.group, view="lanes")
        self.assertEqual([a.name for a in response.context["lanes"]], ["Checking ••0000", "Savings ••1111"])
        self.assertNotContains(response, "••0000 ••0000")
        self.assertContains(response, f'data-partner="t{self.into.pk}"')
        self.assertContains(response, "To Savings ••1111")
        self.assertContains(response, "From Checking ••0000")
        self.assertContains(response, "To elsewhere")  # the stash transfer's partner is private
        self.assertNotContains(response, "Secret stash")
        self.assertNotContains(response, "Stash in")

    def test_the_toolbar_is_icons_export_is_in_settings_and_accounts_inside_filters(self):
        response = self.get(self.alice, self.personal, account=[self.savings.pk])
        html = response.content.decode()
        self.assertNotIn('id="timeline-menu"', html)
        self.assertNotIn("/transactions/export.csv", html)
        self.assertIn("Filters, on", html)
        self.assertIn('aria-label="List"', html)
        self.assertNotIn('form="timeline-filters"', html)
        start = html.index('id="timeline-filters"')
        self.assertIn(f'value="{self.savings.pk}"', html[start:html.index("</form>", start)])
        self.assertTrue(response.context["filtered"])

    def test_a_partner_outside_the_range_is_named_with_its_date(self):
        response = self.get(self.alice, self.personal, view="lanes", end="2026-09-10")
        self.assertContains(response, "To Savings ••1111, Sep 11")

    def test_the_lanes_stop_at_the_row_limit_on_a_whole_day(self):
        Transaction.objects.bulk_create(Transaction(account=self.savings, amount_cents=100, posted_on=day(20 + i % 2), description=f"Bulk {i}") for i in range(6))
        with mock.patch.object(flows, "LANE_LIMIT", 4):
            response = self.get(self.alice, self.personal, view="lanes")
        self.assertContains(response, "Showing the newest")
        days = [d for d, _ in response.context["bands"]]
        self.assertEqual(days, [day(21)])  # Sep 21 has 3 rows; the partial Sep 20 is dropped
