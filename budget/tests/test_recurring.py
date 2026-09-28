from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from budget import recurring
from budget.models import Account, AccountShare, BankConnection, BillReminder, Membership, Recurring, Transaction, Workspace
from budget.reporting import spending

TODAY = date(2026, 9, 28)


def monthly(start, count, day=1):
    return [date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, day) for i in range(count)]


class DetectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared checking")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)

    def add(self, name, days, cents, account=None, classification="expense"):
        for i, day in enumerate(days):
            amount = cents[i] if isinstance(cents, list) else cents
            Transaction.objects.create(account=account or self.shared, posted_on=day, amount_cents=amount, description=name, classification=classification)

    def found(self, user=None):
        return {c["name"]: c for c in recurring.candidates(user or self.bob, self.group, TODAY)}

    def test_series_that_repeat(self):
        self.add("RENT CO", monthly(date(2026, 3, 1), 7), 150000)
        self.add("SPOTIFY #4411", monthly(date(2026, 5, 9), 4, day=9), [1199, 1199, 1250, 1199])  # drift under 10%, store number varies
        self.add("GYM WEEKLY", [TODAY - timedelta(weeks=w) for w in range(5)], 2000)
        self.add("DOMAIN RENEWAL", [date(2024, 9, 20), date(2025, 9, 20), date(2026, 9, 20)], 1500)
        self.add("PAYROLL", monthly(date(2026, 6, 15), 4, day=15), 300000, classification="income")
        self.add("WATER BILL", [date(2026, 5, 3), date(2026, 6, 3), date(2026, 8, 3), date(2026, 9, 3)], 4000)  # July skipped
        found = self.found()
        self.assertEqual({n: (c["interval"], c["kind"]) for n, c in found.items()}, {
            "RENT CO": ("monthly", "bill"), "SPOTIFY": ("monthly", "bill"), "GYM WEEKLY": ("weekly", "bill"),
            "DOMAIN RENEWAL": ("yearly", "bill"), "PAYROLL": ("monthly", "income"), "WATER BILL": ("monthly", "bill")})
        self.assertEqual((found["RENT CO"]["anchor_on"], found["RENT CO"]["amount_cents"], found["RENT CO"]["count"]), (date(2026, 10, 1), 150000, 7))

    def test_what_does_not_count(self):
        self.add("TWICE ONLY", monthly(date(2026, 7, 1), 2), 1000)
        self.add("DRIFTS", monthly(date(2026, 6, 1), 4), [1000, 1000, 1300, 1000])
        self.add("IRREGULAR", [date(2026, 6, 1), date(2026, 6, 20), date(2026, 8, 30), date(2026, 9, 2)], 1000)
        self.add("STOPPED", monthly(date(2025, 11, 1), 4), 1000)
        self.add("SAVINGS MOVE", monthly(date(2026, 6, 1), 4), 1000, classification="transfer")
        self.add("PRIVATE SUB", monthly(date(2026, 6, 1), 4), 1000, account=self.private)
        self.assertEqual(self.found(), {})
        personal = Workspace.objects.get(owner=self.alice, is_personal=True)
        self.assertIn("PRIVATE SUB", {c["name"] for c in recurring.candidates(self.alice, personal, TODAY)})  # the owner still sees it

    @mock.patch("django.utils.timezone.localdate", return_value=TODAY)
    def test_confirm_and_dismiss_take_candidates_away(self, _):
        self.add("RENT CO", monthly(date(2026, 6, 1), 4), 150000)
        self.add("NEWSPAPER", monthly(date(2026, 6, 5), 4, day=5), 900)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.group.pk}/bills/"
        self.assertContains(self.client.get(url), "Found in your transactions")
        self.client.post(url, {"action": "confirm", "pattern": "rent co", "amount_cents": "1"})  # posted amount is ignored
        self.client.post(url, {"action": "dismiss", "pattern": "newspaper"})
        rent = Recurring.objects.get(pattern="rent co")
        self.assertEqual((rent.status, rent.amount_cents, rent.interval, rent.anchor_on), ("confirmed", 150000, "monthly", date(2026, 10, 1)))
        self.assertEqual(Recurring.objects.get(pattern="newspaper").status, "dismissed")
        self.assertEqual(self.found(), {})


class ScheduleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.rent = Recurring.objects.create(workspace=cls.group, name="Rent", pattern="rent", kind="bill", amount_cents=150000, interval="monthly", anchor_on=date(2026, 10, 1))
        cls.pay = Recurring.objects.create(workspace=cls.group, name="Payroll", pattern="payroll", kind="income", amount_cents=300000, interval="monthly", anchor_on=date(2026, 10, 3))

    def test_month_end_dates_clamp(self):
        item = Recurring(interval="monthly", anchor_on=date(2027, 1, 31))
        self.assertEqual(recurring.occurrences(item, date(2027, 1, 1), date(2027, 3, 31)), [date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31)])
        weekly = Recurring(interval="weekly", anchor_on=date(2026, 10, 7))
        self.assertEqual(recurring.occurrences(weekly, date(2026, 9, 28), date(2026, 10, 10)), [date(2026, 9, 30), date(2026, 10, 7)])

    def test_forecast_is_an_estimate_that_never_counts_as_spending(self):
        before = spending(self.alice, self.group, date(2026, 10, 1), date(2026, 10, 31))
        plan = recurring.forecast(self.group, TODAY)
        self.assertEqual((plan["bills_cents"], plan["income_cents"], plan["left_cents"]), (150000, 300000, 150000))
        self.assertEqual([r.name for _, r in plan["items"]], ["Rent", "Payroll"])
        self.assertEqual(spending(self.alice, self.group, date(2026, 10, 1), date(2026, 10, 31)), before)

    @mock.patch("budget.notifications.email_budget_alert")
    @mock.patch("budget.notifications.send_budget_alert")
    def test_reminders_three_days_before_once_each(self, push, email):
        with self.captureOnCommitCallbacks(execute=True):
            recurring.remind(self.group, date(2026, 9, 27))  # four days out: nothing yet
        self.assertFalse(BillReminder.objects.exists())
        with self.captureOnCommitCallbacks(execute=True):
            recurring.remind(self.group, date(2026, 9, 28))
            recurring.remind(self.group, date(2026, 9, 29))
        self.assertEqual(sorted(BillReminder.objects.values_list("recipient__username", "due_on")), [("alice", date(2026, 10, 1)), ("bob", date(2026, 10, 1))])
        push.assert_called_once_with([self.alice.pk, self.bob.pk], "bill")
        email.assert_called_once_with([self.alice.pk, self.bob.pk], "bill")
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        with mock.patch("django.utils.timezone.localdate", return_value=TODAY):
            response = self.client.get("/alerts/")
        self.assertContains(response, "Bill due")
        self.assertContains(response, "Rent")
        Recurring.objects.filter(pk=self.rent.pk).update(remind=False)
        BillReminder.objects.all().delete()
        recurring.remind(self.group, date(2026, 9, 28))
        self.assertFalse(BillReminder.objects.exists())

    def test_typed_names_are_kept_whole(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.group.pk}/bills/new/"
        for name in ("Car payment 1", "Car payment 2"):
            self.assertEqual(self.client.post(url, {"name": name, "kind": "bill", "amount": "300", "interval": "monthly", "anchor_on": "2026-10-05", "remind": "on"}).status_code, 302)
        self.assertEqual(self.client.post(url, {"name": "rent", "kind": "bill", "amount": "1", "interval": "monthly", "anchor_on": "2026-10-05"}).status_code, 400)

    def test_budgets_page_shows_the_next_bill(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        with mock.patch("django.utils.timezone.localdate", return_value=TODAY):
            self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/budgets/"), "Rent")


class DailyTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        Recurring.objects.create(workspace=cls.personal, name="Rent", pattern="rent", kind="bill", amount_cents=150000, interval="monthly", anchor_on=timezone.localdate() + timedelta(days=2))

    def run_daily(self, token):
        return self.client.post("/tasks/daily/", HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_needs_the_token(self):
        self.assertEqual(self.run_daily("anything").status_code, 404)  # not configured
        with override_settings(TASKS_TOKEN="synthetic-task-token"):
            self.assertEqual(self.run_daily("wrong").status_code, 404)
            self.assertEqual(self.client.get("/tasks/daily/").status_code, 405)

    @override_settings(TASKS_TOKEN="synthetic-task-token", PLAID_CLIENT_ID="c", PLAID_SECRET="s", PLAID_TOKEN_KEY="k")
    def test_reminders_and_catch_up_sync_for_stale_connections(self):
        now = timezone.now()
        stale = BankConnection.objects.create(owner=self.alice, item_id="item-stale", access_token="x", last_synced_at=now - timedelta(hours=7))
        BankConnection.objects.create(owner=self.alice, item_id="item-fresh", access_token="x", last_synced_at=now - timedelta(hours=1))
        with mock.patch("budget.plaid.sync", return_value=("ok", 0)) as sync:
            self.assertEqual(self.run_daily("synthetic-task-token").status_code, 200)
        self.assertEqual([c.args[0].pk for c in sync.call_args_list], [stale.pk])
        self.assertTrue(BillReminder.objects.filter(recipient=self.alice).exists())
