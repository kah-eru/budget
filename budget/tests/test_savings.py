from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from budget import plaid as bank
from budget.models import Account, AccountShare, BankConnection, Membership, Transaction, Workspace
from budget.reporting import savings, spending
from budget.tests.test_plaid import KEYS, page, txn

SEP = (date(2026, 9, 1), date(2026, 9, 30))


class SavingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.checking = Account.objects.create(owner=cls.alice, name="Checking")
        cls.savings = Account.objects.create(owner=cls.alice, name="Savings", is_savings=True, balance_kind="asset", balance_cents=1240000)
        cls.high_yield = Account.objects.create(owner=cls.alice, name="Secret high-yield", is_savings=True, balance_kind="asset", balance_cents=500000)
        for a in (cls.checking, cls.savings):
            AccountShare.objects.create(account=a, workspace=cls.group)
        t = Transaction.objects.create
        t(account=cls.savings, amount_cents=50000, posted_on=date(2026, 9, 16), classification="transfer", money_in=True, description="From checking")
        t(account=cls.checking, amount_cents=50000, posted_on=date(2026, 9, 16), classification="transfer", description="To savings")
        t(account=cls.savings, amount_cents=30000, posted_on=date(2026, 9, 20), classification="transfer", description="To checking")
        t(account=cls.savings, amount_cents=1200, posted_on=date(2026, 9, 28), classification="income", money_in=True, description="Interest")
        t(account=cls.savings, amount_cents=9900, posted_on=date(2026, 9, 29), classification="transfer", pending=True, description="Pending out")
        t(account=cls.savings, amount_cents=20000, posted_on=date(2026, 9, 21), classification="transfer", description="To high-yield")
        t(account=cls.high_yield, amount_cents=20000, posted_on=date(2026, 9, 21), classification="transfer", money_in=True, description="From savings")
        t(account=cls.savings, amount_cents=10000, posted_on=date(2026, 8, 16), classification="transfer", money_in=True, description="August")

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_money_in_and_out_by_the_banks_direction_posted_only(self):
        s = savings(self.alice, self.personal, *SEP)
        # In: 500 + 12 + 200 (into high-yield); out: 300 + 200 (to high-yield). Pending stays out.
        self.assertEqual((s["in_cents"], s["out_cents"], s["net_cents"]), (71200, 50000, 21200))
        self.assertEqual(s["balance_cents"], 1740000)
        self.assertEqual([d["cumulative_cents"] for d in s["days"] if d["day"] in (date(2026, 9, 16), date(2026, 9, 20), date(2026, 9, 30))], [50000, 20000, 21200])
        self.assertEqual(s["days"][20]["posted_cents"], 0)  # Sep 21: savings to high-yield nets out
        self.assertEqual(spending(self.alice, self.personal, *SEP)["posted_cents"], 0)  # moving money is never spending

    def test_the_group_sees_only_shared_savings(self):
        s = savings(self.bob, self.group, *SEP)
        self.assertEqual([a.name for a in s["accounts"]], ["Savings"])
        self.assertEqual((s["in_cents"], s["out_cents"]), (51200, 50000))
        self.login(self.bob)
        response = self.client.get(f"/workspaces/{self.group.pk}/savings/", {"period": "2026-09"})
        self.assertContains(response, "Savings")
        self.assertNotContains(response, "Secret high-yield")
        self.login(self.eve)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/savings/").status_code, 404)

    def test_page_compares_periods_links_the_timeline_and_overview_shows_a_card(self):
        self.login(self.alice)
        response = self.client.get(f"/workspaces/{self.personal.pk}/savings/", {"period": "2026-09"})
        self.assertEqual(response.context["change_cents"], 21200 - 10000)
        self.assertContains(response, f"account={self.savings.pk}")
        self.assertContains(response, "view=lanes")
        year = self.client.get(f"/workspaces/{self.personal.pk}/savings/", {"period": "2026"})
        self.assertEqual(len(year.context["saved"]["months"]), 12)
        lifetime = self.client.get(f"/workspaces/{self.personal.pk}/savings/", {"period": "all"})
        self.assertIsNone(lifetime.context["change_cents"])
        self.assertContains(lifetime, "Lifetime: +$312.00 saved")  # August's 100 plus September's 212
        self.assertContains(lifetime, "since August 2026")
        self.assertContains(lifetime, "span=all")
        # Overview's top card switches to Savings in place, with the same period, change and Timeline link.
        overview = self.client.get(f"/workspaces/{self.personal.pk}/", {"period": "2026-09"})
        self.assertContains(overview, 'data-mode="savings"')
        self.assertEqual(overview.context["saved"]["change_cents"], 11200)
        self.assertContains(overview, f"/workspaces/{self.personal.pk}/savings/")
        self.assertContains(overview, "View savings transactions")
        Account.objects.filter(is_savings=True).update(is_savings=False)
        overview = self.client.get(f"/workspaces/{self.personal.pk}/", {"period": "2026-09"})
        self.assertContains(overview, "No savings accounts yet")
        self.assertNotContains(overview, f"/workspaces/{self.personal.pk}/savings/")

    def test_the_savings_mode_cookie_turns_the_timeline_and_export_to_savings_accounts(self):
        self.login(self.alice)
        url, sep = f"/workspaces/{self.personal.pk}/transactions/", {"start": "2026-09-01", "end": "2026-09-30"}
        spending_view = self.client.get(url, sep)
        self.assertContains(spending_view, "To savings")  # the checking side
        self.assertNotContains(spending_view, "Saved so far")
        self.client.cookies["mode"] = "savings"
        response = self.client.get(url, sep)
        self.assertNotContains(response, "To savings")
        self.assertContains(response, "Saved so far")
        self.assertEqual(set(response.context["form"].fields["account"].queryset), {self.savings, self.high_yield})
        s = savings(self.alice, self.personal, *SEP)
        self.assertEqual(response.context["totals"], {"in_cents": s["in_cents"], "out_cents": s["out_cents"], "posted_cents": s["net_cents"]})
        export = self.client.get(url + "export.csv", sep).content.decode()
        self.assertIn("From checking", export)
        self.assertNotIn("To savings", export)
        # One mode for both tabs: Overview renders it before paint.
        overview = self.client.get(f"/workspaces/{self.personal.pk}/")
        self.assertContains(overview, '<html lang="en" data-overview-mode="savings">')
        # A group sees only the shared savings account.
        self.login(self.bob)
        group = self.client.get(f"/workspaces/{self.group.pk}/transactions/", sep)
        self.assertEqual(list(group.context["form"].fields["account"].queryset), [self.savings])
        self.assertNotContains(group, "Secret high-yield")
        self.assertNotContains(group, "From savings")
        Account.objects.filter(is_savings=True).update(is_savings=False)
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/transactions/", sep), "No savings accounts yet")

    def test_the_owner_switch_marks_savings(self):
        self.login(self.alice)
        self.client.post(f"/workspaces/{self.personal.pk}/accounts/{self.checking.pk}/edit/", {"name": "Checking", "balance_kind": "", "is_savings": "on"})
        self.assertTrue(Account.objects.get(pk=self.checking.pk).is_savings)
        self.client.post(f"/workspaces/{self.personal.pk}/accounts/{self.checking.pk}/edit/", {"name": "Checking", "balance_kind": ""})
        self.assertIs(Account.objects.get(pk=self.checking.pk).is_savings, False)


@override_settings(**KEYS)
class SyncedSavingsTests(TestCase):
    def test_the_bank_type_marks_savings_until_the_owner_chooses(self):
        alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        connection = BankConnection.objects.create(owner=alice, item_id="item-1", access_token=bank.encrypt("access-sandbox-1"))
        offered = {"institution_id": "ins_1", "accounts": [
            {"id": "acc-1", "name": "Plaid Saving", "mask": "1111", "type": "depository", "subtype": "savings", "current": Decimal("100.00"), "currency": "USD"},
            {"id": "acc-2", "name": "Plaid Checking", "mask": "0000", "type": "depository", "subtype": "checking", "current": Decimal("5.00"), "currency": "USD"}]}
        self.client.force_login(alice, backend="django.contrib.auth.backends.ModelBackend")
        with mock.patch("budget.plaid.accounts", return_value=offered), mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]):
            self.client.post(f"/banks/{connection.pk}/accounts/", {"accounts": ["acc-1", "acc-2"]})
        self.assertEqual(dict(Account.objects.values_list("provider_account_id", "is_savings")), {"acc-1": True, "acc-2": False})
        # An account imported before this existed gets the bank's answer on its next sync; the owner's choice then sticks.
        Account.objects.filter(provider_account_id="acc-1").update(is_savings=None)
        Account.objects.filter(provider_account_id="acc-2").update(is_savings=True)
        with mock.patch("budget.plaid.accounts", return_value=offered):
            bank.record_balances(connection)
        self.assertEqual(dict(Account.objects.values_list("provider_account_id", "is_savings")), {"acc-1": True, "acc-2": True})
