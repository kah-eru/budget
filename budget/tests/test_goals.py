from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.goals import progress
from budget.models import Account, AccountShare, Goal, Membership, Workspace

TODAY = date(2026, 9, 28)


class GoalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.savings = Account.objects.create(owner=cls.alice, name="Savings", balance_kind="asset", balance_cents=500000)
        cls.card = Account.objects.create(owner=cls.alice, name="Card", balance_kind="liability", balance_cents=210000)
        cls.private = Account.objects.create(owner=cls.alice, name="Private savings", balance_kind="asset", balance_cents=100)
        AccountShare.objects.create(account=cls.savings, workspace=cls.group)

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_off_until_turned_on(self):
        self.login(self.bob)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/goals/").status_code, 404)
        self.assertContains(self.client.get("/settings/"), "Turn on goals")
        self.assertNotContains(self.client.get(f"/workspaces/{self.group.pk}/budgets/"), "goals-title")
        self.client.post("/settings/goals/", {"on": "1"})
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/goals/").status_code, 200)
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/budgets/"), "goals-title")
        self.client.post("/settings/goals/", {"on": "0"})
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/goals/new/").status_code, 404)

    def test_savings_progress_and_the_monthly_amount(self):
        manual = Goal.objects.create(workspace=self.personal, name="Emergency fund", kind="savings", target_cents=1000000, manual_cents=620000, target_date=date(2027, 6, 30))
        p = progress(manual, self.alice, TODAY)
        self.assertEqual((p["done_cents"], p["remaining_cents"], p["percent"], p["monthly_cents"]), (620000, 380000, 62, 42223))  # 9 months left
        linked = Goal.objects.create(workspace=self.group, name="Trip", kind="savings", target_cents=400000, account=self.savings)
        p = progress(linked, self.bob, TODAY)
        self.assertEqual((p["done_cents"], p["percent"], p["monthly_cents"], p["linked"]), (500000, 100, None, self.savings))
        late = Goal.objects.create(workspace=self.personal, name="Late", kind="savings", target_cents=10000, manual_cents=2500, target_date=date(2026, 1, 1))
        p = progress(late, self.alice, TODAY)
        self.assertEqual((p["monthly_cents"], p["overdue"]), (7500, True))

    def test_debt_payoff_counts_from_the_balance_when_linked(self):
        self.login(self.alice)
        self.client.post("/settings/goals/", {"on": "1"})
        self.client.post(f"/workspaces/{self.personal.pk}/goals/new/", {"name": "Pay off card", "kind": "debt", "target": "3000.00", "account": self.card.pk})
        goal = Goal.objects.get(name="Pay off card")
        self.assertEqual(goal.start_cents, 210000)
        Account.objects.filter(pk=self.card.pk).update(balance_cents=150000)
        p = progress(goal, self.alice, TODAY)
        self.assertEqual((p["done_cents"], p["percent"]), (60000, 20))

    def test_groups_link_only_shared_accounts_and_fall_back_when_unshared(self):
        self.login(self.bob)
        self.client.post("/settings/goals/", {"on": "1"})
        url = f"/workspaces/{self.group.pk}/goals/new/"
        self.assertEqual(self.client.post(url, {"name": "Sneaky", "kind": "savings", "target": "10.00", "account": self.private.pk}).status_code, 400)
        self.assertEqual(self.client.post(url, {"name": "Mismatch", "kind": "debt", "target": "10.00", "account": self.savings.pk}).status_code, 400)
        goal = Goal.objects.create(workspace=self.group, name="Trip", kind="savings", target_cents=400000, account=self.savings, manual_cents=1000)
        AccountShare.objects.filter(account=self.savings, workspace=self.group).delete()
        self.assertEqual(progress(goal, self.bob, TODAY)["done_cents"], 1000)
