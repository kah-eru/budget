from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, Budget, Category, Transaction, TransactionAnnotation, Workspace
from budget.reporting import budget_progress, disposable

MAY_20 = date(2026, 5, 20)


class BudgetKindTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "eve")]
        cls.ws = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.card = Account.objects.create(owner=cls.alice, name="Checking")
        cls.cat = {c.name: c for c in Category.objects.filter(workspace=cls.ws)}

    def budget(self, kind, cents, category, period="month", **kw):
        return Budget.objects.create(workspace=self.ws, kind=kind, limit_cents=cents, category=self.cat[category], period=period, **kw)

    def spend(self, cents, day, category=None, **kw):
        row = Transaction.objects.create(account=self.card, amount_cents=cents, posted_on=day, description="x", **kw)
        if category:
            TransactionAnnotation.objects.create(transaction=row, workspace=self.ws, category=self.cat[category], category_source="manual")

    def test_irregular_cost_sets_aside_a_twelfth_each_month(self):
        insurance = self.budget("irregular", 120000, "Health", period="year")
        self.spend(30000, date(2026, 2, 1), "Health")
        p = budget_progress(self.alice, self.ws, [insurance], MAY_20)[0]
        self.assertEqual((p["set_aside_monthly_cents"], p["set_aside_to_date_cents"], p["spent_cents"]), (10000, 50000, 30000))

    def test_fixed_bill_is_paid_once_the_amount_posts(self):
        rent = self.budget("fixed", 150000, "Housing", due_day=1)
        p = budget_progress(self.alice, self.ws, [rent], MAY_20)[0]
        self.assertFalse(p["paid"])
        self.spend(150000, date(2026, 5, 1), "Housing")
        self.assertTrue(budget_progress(self.alice, self.ws, [rent], MAY_20)[0]["paid"])

    def test_disposable_income_from_expected_income(self):
        Workspace.objects.filter(pk=self.ws.pk).update(expected_income_cents=500000)
        self.ws.refresh_from_db()
        self.budget("fixed", 150000, "Housing", due_day=1)
        self.budget("irregular", 120000, "Health", period="year")
        self.budget("flexible", 30000, "Dining")
        self.budget("flexible", 120000, "Travel", period="year")
        d = disposable(self.alice, self.ws, MAY_20)
        self.assertEqual(d["income_source"], "expected")
        self.assertEqual((d["fixed_cents"], d["set_aside_cents"], d["disposable_cents"]), (150000, 10000, 340000))
        self.assertEqual((d["flexible_cents"], d["left_cents"]), (40000, 300000))

    def test_income_falls_back_to_three_complete_months_average(self):
        for cents, day in ((300000, date(2026, 2, 15)), (330000, date(2026, 4, 15)), (999999, date(2026, 5, 2)), (100000, date(2026, 1, 31))):
            self.spend(cents, day, classification="income")
        self.spend(50000, date(2026, 3, 3), classification="income", pending=True)
        d = disposable(self.alice, self.ws, MAY_20)
        self.assertEqual((d["income_source"], d["income_cents"]), ("average", 210000))  # (3000 + 0 + 3300) / 3

    def test_form_ties_kind_to_period_and_due_day_and_income_can_be_set(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.ws.pk}/budgets/new/"
        self.client.post(url, {"kind": "irregular", "category": self.cat["Health"].pk, "period": "month", "limit": "1200", "due_day": "5"})
        b = Budget.objects.get(kind="irregular")
        self.assertEqual((b.period, b.due_day), ("year", None))
        self.client.post(url, {"kind": "fixed", "category": self.cat["Housing"].pk, "period": "year", "limit": "1500", "due_day": "1"})
        self.assertEqual(Budget.objects.get(kind="fixed").period, "month")
        self.assertEqual(self.client.post(url, {"kind": "fixed", "category": self.cat["Utilities"].pk, "period": "month", "limit": "90", "due_day": "32"}).status_code, 400)
        self.client.post(f"/workspaces/{self.ws.pk}/budgets/income/", {"income": "5000"})
        self.ws.refresh_from_db()
        self.assertEqual(self.ws.expected_income_cents, 500000)
        self.client.post(f"/workspaces/{self.ws.pk}/budgets/income/", {"income": ""})
        self.ws.refresh_from_db()
        self.assertIsNone(self.ws.expected_income_cents)
        self.client.force_login(self.eve, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.post(f"/workspaces/{self.ws.pk}/budgets/income/", {"income": "1"}).status_code, 404)
