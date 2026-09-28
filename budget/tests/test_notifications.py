from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, BudgetAlert, Category, Membership, Transaction, TransactionAnnotation, Workspace
from budget.notifications import evaluate

TODAY = date(2026, 5, 20)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class BudgetAlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.carol = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "carol")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Shared card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")

    def setUp(self):
        self.budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=10000)

    def spend(self, cents, day=TODAY, **kwargs):
        row = Transaction.objects.create(account=self.card, amount_cents=cents, posted_on=day, description="Cafe", **kwargs)
        TransactionAnnotation.objects.create(transaction=row, workspace=self.group, category=self.dining, category_source="manual")
        evaluate(self.group)
        return row

    def inbox(self, user):
        return BudgetAlert.objects.filter(recipient=user, silent=False)

    def test_crossing_alerts_each_member_once_per_period(self, _):
        self.spend(10000)
        self.assertEqual(BudgetAlert.objects.count(), 0)  # exactly at the limit is not over
        self.spend(900, pending=True)
        self.assertEqual(BudgetAlert.objects.count(), 0)  # pending never triggers
        self.spend(1)
        self.assertEqual({a.recipient for a in BudgetAlert.objects.all()}, {self.alice, self.bob})
        self.spend(500, classification="refund")
        self.spend(600)  # refund, then a second crossing in the same period
        self.assertEqual(BudgetAlert.objects.count(), 2)

    def test_new_period_alerts_again_and_closed_periods_never_do(self, localdate):
        self.spend(20000, day=date(2026, 4, 3))  # April is closed on May 20
        self.assertEqual(BudgetAlert.objects.count(), 0)
        self.spend(10001)
        localdate.return_value = date(2026, 6, 2)
        self.spend(10001, day=date(2026, 6, 1))
        self.assertEqual(sorted({a.period_start for a in BudgetAlert.objects.all()}), [date(2026, 5, 1), date(2026, 6, 1)])

    def test_creating_or_editing_a_budget_sets_a_silent_baseline(self, _):
        self.spend(5000)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.client.post(f"/workspaces/{self.group.pk}/budgets/{self.budget.pk}/", {"category": self.dining.pk, "period": "month", "limit": "40"})
        self.spend(100)
        self.assertEqual(self.inbox(self.alice).count() + self.inbox(self.bob).count(), 0)
        self.assertEqual(BudgetAlert.objects.filter(silent=True).count(), 2)

    def test_new_member_gets_a_baseline_not_past_alerts(self, _):
        self.spend(10001)
        from budget.notifications import baseline_member
        Membership.objects.create(workspace=self.group, user=self.carol)
        baseline_member(self.group, self.carol)
        self.spend(100)
        self.assertEqual(self.inbox(self.carol).count(), 0)

    def test_inbox_lists_marks_read_and_hides_revoked_workspaces(self, _):
        self.spend(10250)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/"), "1 new alert")
        page = self.client.get("/alerts/").content.decode()
        self.assertIn("Dining", page)
        self.assertIn("$2.50 over", page)
        self.assertFalse(self.inbox(self.bob).filter(read_at=None).exists())
        Membership.objects.filter(user=self.bob).delete()
        self.assertNotIn("Dining", self.client.get("/alerts/").content.decode())
