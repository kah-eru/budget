from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, Category, Membership, Transaction, TransactionAnnotation, Workspace
from budget.reporting import budget_progress

MAY = date(2026, 5, 1)


class BudgetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")

    def spend(self, cents, day=date(2026, 5, 10), account=None, category=None, description="Cafe", **kwargs):
        row = Transaction.objects.create(account=account or self.shared, amount_cents=cents, posted_on=day, description=description, **kwargs)
        if category:
            TransactionAnnotation.objects.create(transaction=row, workspace=self.group, category=category, category_source="manual")
        return row

    def progress(self, budget, day=MAY):
        return budget_progress(self.bob, self.group, [budget], day)[0]

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_limit_boundary_is_inclusive(self):
        budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=10000)
        self.spend(10000, category=self.dining)
        p = self.progress(budget)
        self.assertEqual((p["spent_cents"], p["remaining_cents"], p["over"]), (10000, 0, False))
        self.spend(1, category=self.dining)
        p = self.progress(budget)
        self.assertEqual((p["remaining_cents"], p["over"]), (-1, True))

    def test_pending_is_separate_refunds_reduce_other_periods_and_private_accounts_ignored(self):
        budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=5000)
        self.spend(4000, category=self.dining)
        self.spend(900, category=self.dining, pending=True)
        self.spend(1500, category=self.dining, classification="refund")
        self.spend(7000, category=self.dining, day=date(2026, 4, 30))
        self.spend(7000, category=None, account=self.private)
        p = self.progress(budget)
        self.assertEqual((p["spent_cents"], p["pending_cents"], p["over"]), (2500, 900, False))

    def test_name_match_budget_normalizes_and_yearly_period_spans_the_year(self):
        budget = Budget.objects.create(workspace=self.group, name_match="starbucks", period="year", limit_cents=20000)
        self.spend(450, description="  STARBUCKS   #12", day=date(2026, 1, 3))
        self.spend(550, description="Starbucks Reserve", day=date(2026, 11, 3))
        self.spend(9999, description="Bakery", day=date(2026, 6, 1))
        self.spend(450, description="Starbucks", day=date(2025, 12, 31))
        p = self.progress(budget)
        self.assertEqual((p["spent_cents"], p["start"], p["end"]), (1000, date(2026, 1, 1), date(2026, 12, 31)))

    def test_overview_shows_progress_and_form_validates_target_and_amount(self):
        self.login(self.bob)
        url = f"/workspaces/{self.group.pk}/budgets/new/"
        self.assertEqual(self.client.post(url, {"period": "month", "limit": "50"}).status_code, 400)  # no target
        both = {"category": self.dining.pk, "name_match": "cafe", "period": "month", "limit": "50"}
        self.assertEqual(self.client.post(url, both).status_code, 400)
        foreign = Category.objects.get(workspace__owner=self.alice, workspace__is_personal=True, name="Dining")
        self.assertEqual(self.client.post(url, {"category": foreign.pk, "period": "month", "limit": "50"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"category": self.dining.pk, "period": "month", "limit": "0"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"category": self.dining.pk, "period": "month", "limit": "50"}).status_code, 302)
        self.spend(6025, category=self.dining)
        page = self.client.get(f"/workspaces/{self.group.pk}/", {"period": "2026-05"}).content.decode()
        self.assertIn("$10.25 over", page)

    def test_delete_and_outsiders(self):
        budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=5000)
        self.login(self.eve)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/budgets/").status_code, 404)
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/budgets/{budget.pk}/delete/").status_code, 404)
        self.login(self.bob)
        self.client.post(f"/workspaces/{self.group.pk}/budgets/{budget.pk}/delete/")
        self.assertFalse(Budget.objects.exists())
