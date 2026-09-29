from datetime import date
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, Category, Membership, Rule, Transaction, TransactionAnnotation, Workspace
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
        page = self.client.get(f"/workspaces/{self.group.pk}/budgets/", {"period": "2026-05"}).content.decode()
        self.assertIn("$10.25 over", page)

    def test_year_view_counts_monthly_budgets_twelve_times_and_totals_match_the_period(self):
        monthly = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=40000)
        yearly = Budget.objects.create(workspace=self.group, name_match="insurance", period="year", limit_cents=120000)
        self.spend(50000, category=self.dining)  # May, $100 over the month
        self.spend(10000, day=date(2026, 2, 3), category=self.dining)
        self.spend(60000, description="Car insurance")
        year = (date(2026, 1, 1), date(2026, 12, 31))
        p = budget_progress(self.bob, self.group, [monthly, yearly], MAY, span=year)
        self.assertEqual([(r["spent_cents"], r["limit_cents"], r["start"]) for r in p], [(60000, 480000, year[0]), (60000, 120000, year[0])])
        self.login(self.bob)
        page = self.client.get(f"/workspaces/{self.group.pk}/budgets/", {"period": "2026"})
        self.assertEqual(page.context["budget_totals"], {"limit_cents": 600000, "spent_cents": 120000, "left_cents": 480000, "over_cents": 0})
        page = self.client.get(f"/workspaces/{self.group.pk}/budgets/", {"period": "2026-05"})
        # A yearly budget shows in a month but stays out of that month's total.
        self.assertEqual(page.context["budget_totals"], {"limit_cents": 40000, "spent_cents": 50000, "left_cents": 0, "over_cents": 10000})
        # Budgets live on the Budget tab now, not on the Overview.
        overview = self.client.get(f"/workspaces/{self.group.pk}/", {"period": "2026-05"})
        self.assertNotContains(overview, "data-panel")
        self.assertNotContains(overview, "By category")
        self.assertNotContains(overview, "Manage budgets")

    def test_budget_tab_lists_every_category_and_the_category_page_manages_it(self):
        Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=5000)
        Budget.objects.create(workspace=self.group, name_match="netflix", limit_cents=1500)
        self.spend(2500, category=self.dining)
        self.spend(700, description="Misc")
        self.login(self.bob)
        g = self.group.pk
        tab = self.client.get(f"/workspaces/{g}/budgets/", {"period": "2026-05"})
        rows = {r["category"].name: r for r in tab.context["rows"]}
        self.assertEqual(set(rows), set(self.group.categories.filter(archived=False).values_list("name", flat=True)))  # even with no spending
        self.assertEqual((rows["Dining"]["limit"]["spent_cents"], rows["Dining"]["limit"]["limit_cents"]), (2500, 5000))
        self.assertIsNone(rows["Groceries"]["limit"])
        self.assertContains(tab, "No limit")
        self.assertEqual(tab.context["uncategorized"]["posted_cents"], 700)
        self.assertEqual([p["budget"].name_match for p in tab.context["others"]], ["netflix"])
        self.assertContains(tab, f'href="/workspaces/{g}/categories/{self.dining.pk}/?period=2026-05"')
        # A category added from the tab comes back to the tab, on the same period.
        added = self.client.post(f"/workspaces/{g}/categories/", {"name": "Pets", "period": "2026-05"})
        self.assertRedirects(added, f"/workspaces/{g}/budgets/?period=2026-05", fetch_redirect_response=False)
        # The category page: its limit, its rules, and its recent transactions.
        Rule.objects.create(workspace=self.group, kind="contains", pattern="CAFE", category=self.dining)
        here = f"/workspaces/{g}/categories/{self.dining.pk}/?period=2026-05"
        page = self.client.get(here)
        self.assertEqual([p["limit_cents"] for p in page.context["limits"]], [5000])
        self.assertEqual([r.pattern for r in page.context["rules"]], ["CAFE"])
        self.assertEqual([r.amount_cents for r in page.context["recent"]], [2500])
        self.assertContains(page, "Add another limit")
        # Set a limit starts on this category and returns here; a link off the site falls back to the Budget tab.
        new = f"/workspaces/{g}/budgets/new/"
        self.assertEqual(self.client.get(new, {"category": self.dining.pk, "next": here}).context["form"].initial["category"], str(self.dining.pk))
        saved = self.client.post(f"{new}?category={self.dining.pk}&next={quote(here)}", {"category": self.dining.pk, "period": "year", "limit": "600"})
        self.assertRedirects(saved, here, fetch_redirect_response=False)
        outside = self.client.post(f"{new}?next=https://example.com/", {"category": self.dining.pk, "period": "year", "limit": "700"})
        self.assertRedirects(outside, f"/workspaces/{g}/budgets/", fetch_redirect_response=False)

    def test_delete_and_outsiders(self):
        budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=5000)
        self.login(self.eve)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/budgets/").status_code, 404)
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/budgets/{budget.pk}/delete/").status_code, 404)
        self.login(self.bob)
        self.client.post(f"/workspaces/{self.group.pk}/budgets/{budget.pk}/delete/")
        self.assertFalse(Budget.objects.exists())
