from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from budget import plaid as bank
from budget.models import Account, AccountShare, BankConnection, Membership, Workspace
from budget.reporting import net_worth
from budget.tests.test_plaid import KEYS, page, txn


class NetWorthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.home = Account.objects.create(owner=cls.alice, name="Home", balance_kind="asset", balance_cents=40000000)
        cls.checking = Account.objects.create(owner=cls.alice, name="Checking", balance_kind="asset", balance_cents=-2500)  # overdrawn
        cls.loan = Account.objects.create(owner=cls.alice, name="Car loan", balance_kind="liability", balance_cents=1230000)
        cls.wallet = Account.objects.create(owner=cls.alice, name="Old wallet")
        for account in (cls.checking, cls.loan):
            AccountShare.objects.create(account=account, workspace=cls.group)

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_own_minus_owe_and_groups_see_only_shared_accounts(self):
        worth = net_worth(self.alice, self.personal)
        self.assertEqual((worth["own_cents"], worth["owe_cents"], worth["net_cents"]), (39997500, 1230000, 38767500))
        self.assertEqual([a.name for a in worth["uncounted"]], ["Old wallet"])
        group = net_worth(self.bob, self.group)
        self.assertEqual((group["own_cents"], group["owe_cents"]), (-2500, 1230000))
        self.assertNotIn("Home", [a.name for a in group["assets"]])
        self.login(self.bob)
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/net-worth/"), "-$12,325.00")
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/"), "Net worth")

    def test_manual_values_are_the_owners_to_set(self):
        self.login(self.alice)
        url = f"/workspaces/{self.personal.pk}/accounts/{self.wallet.pk}/edit/"
        self.assertEqual(self.client.post(url, {"name": "Old wallet", "balance_kind": "asset", "balance": ""}).status_code, 400)  # a value is needed
        self.client.post(url, {"name": "Old wallet", "balance_kind": "asset", "balance": "40.50"})
        self.wallet.refresh_from_db()
        self.assertEqual((self.wallet.balance_kind, self.wallet.balance_cents), ("asset", 4050))
        self.assertIsNotNone(self.wallet.balance_updated_at)
        self.login(self.bob)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/accounts/{self.loan.pk}/edit/").status_code, 404)

    def test_add_something_you_own(self):
        self.login(self.alice)
        self.assertContains(self.client.get("/accounts/new/?kind=liability"), 'value="liability" selected')
        self.client.post("/accounts/new/", {"name": "Student loan", "balance_kind": "liability", "balance": "9000"})
        self.assertEqual(Account.objects.get(name="Student loan").balance_cents, 900000)


@override_settings(**KEYS)
class SyncedBalanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)

    def setUp(self):
        self.connection = BankConnection.objects.create(owner=self.alice, item_id="item-1", access_token=bank.encrypt("access-sandbox-1"))
        self.checking = Account.objects.create(owner=self.alice, name="Plaid Checking", connection=self.connection, provider_account_id="acc-1")
        self.card = Account.objects.create(owner=self.alice, name="Plaid Card", connection=self.connection, provider_account_id="acc-2")

    def offered(self, checking="110.00", card="410.25"):
        return {"institution_id": "ins_1", "accounts": [
            {"id": "acc-1", "name": "Plaid Checking", "mask": "0000", "type": "depository", "subtype": "checking", "current": Decimal(checking), "currency": "USD"},
            {"id": "acc-2", "name": "Plaid Card", "mask": "3333", "type": "credit", "subtype": "credit card", "current": Decimal(card), "currency": "USD"}]}

    def sync(self, **balances):
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]), \
             mock.patch("budget.plaid.accounts", return_value=self.offered(**balances)):
            return bank.sync(self.connection)

    def test_a_sync_records_balances_and_the_owners_choice_sticks(self):
        self.sync()
        self.checking.refresh_from_db()
        self.card.refresh_from_db()
        self.assertEqual((self.checking.balance_kind, self.checking.balance_cents), ("asset", 11000))
        self.assertEqual((self.card.balance_kind, self.card.balance_cents), ("liability", 41025))
        Account.objects.filter(pk=self.card.pk).update(balance_kind="")  # the owner chose "Not counted"
        self.sync(card="99.00")
        self.card.refresh_from_db()
        self.assertEqual((self.card.balance_kind, self.card.balance_cents), ("", 9900))
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        response = self.client.post(f"/workspaces/{self.personal.pk}/accounts/{self.checking.pk}/edit/",
                                    {"name": "Checking", "balance_kind": "asset", "balance": "999999.00"})
        self.assertEqual(response.status_code, 302)
        self.checking.refresh_from_db()
        self.assertEqual((self.checking.name, self.checking.balance_cents), ("Checking", 11000))  # a synced balance can't be typed over

    def test_a_balance_failure_never_fails_the_sync(self):
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]), \
             mock.patch("budget.plaid.accounts", side_effect=bank.PlaidError("INTERNAL_SERVER_ERROR")):
            self.assertEqual(bank.sync(self.connection)[0], "ok")
        self.checking.refresh_from_db()
        self.assertIsNone(self.checking.balance_cents)
