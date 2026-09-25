from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, Category, Membership, SplitLine, Transaction, TransactionAnnotation, Workspace
from budget.reporting import budget_progress, by_category, visible_transactions

MAY = (date(2026, 5, 1), date(2026, 5, 31))


class SplitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.cat = {c.name: c for c in Category.objects.filter(workspace=cls.group)}
        cls.big = Transaction.objects.create(account=cls.card, amount_cents=5000, posted_on=date(2026, 5, 2), description="SUPERSTORE")
        cls.refund = Transaction.objects.create(account=cls.card, amount_cents=1000, posted_on=date(2026, 5, 3), description="SUPERSTORE RETURN", classification="refund")
        TransactionAnnotation.objects.create(transaction=cls.big, workspace=cls.group, category=cls.cat["Travel"], category_source="manual")

    def url(self, row):
        return f"/workspaces/{self.group.pk}/accounts/{self.card.pk}/transactions/{row.pk}/split/"

    def split(self, row, *lines):
        data = {}
        for i, (name, amount) in enumerate(lines):
            data[f"category_{i}"], data[f"amount_{i}"] = self.cat[name].pk, amount
        return self.client.post(self.url(row), data)

    def setUp(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")

    def totals(self):
        return {t["name"]: t["posted_cents"] for t in by_category(visible_transactions(self.bob, self.group), *MAY, self.group)}

    def test_lines_must_add_up_exactly_and_use_this_workspaces_categories(self):
        self.assertEqual(self.split(self.big, ("Groceries", "30.00"), ("Shopping", "19.99")).status_code, 400)
        self.assertEqual(self.split(self.big, ("Groceries", "50.00")).status_code, 400)  # one line is not a split
        foreign = Category.objects.get(workspace=self.personal, name="Dining")
        response = self.client.post(self.url(self.big), {"category_0": foreign.pk, "amount_0": "30", "category_1": self.cat["Shopping"].pk, "amount_1": "20"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SplitLine.objects.exists())
        self.assertEqual(self.split(self.big, ("Groceries", "30.00"), ("Shopping", "20.00")).status_code, 302)
        self.assertEqual(sorted(SplitLine.objects.values_list("amount_cents", flat=True)), [2000, 3000])

    def test_reports_and_budgets_count_each_line_and_ignore_the_single_category(self):
        self.split(self.big, ("Groceries", "30.00"), ("Shopping", "20.00"))
        self.split(self.refund, ("Groceries", "4.00"), ("Shopping", "6.00"))
        self.assertEqual(self.totals(), {"Groceries": 2600, "Shopping": 1400})
        budget = Budget.objects.create(workspace=self.group, category=self.cat["Groceries"], limit_cents=2500)
        p = budget_progress(self.bob, self.group, [budget], date(2026, 5, 20))[0]
        self.assertEqual((p["spent_cents"], p["over"]), (2600, True))
        personal_totals = {t["name"]: t["posted_cents"] for t in by_category(visible_transactions(self.alice, self.personal), *MAY, self.personal)}
        self.assertEqual(personal_totals, {"Uncategorized": 4000})  # the split lives in the group only

    def test_timeline_filter_finds_split_rows_under_each_line_and_csv_lists_lines(self):
        self.split(self.big, ("Groceries", "30.00"), ("Shopping", "20.00"))
        list_url = f"/workspaces/{self.group.pk}/transactions/"
        for name in ("Groceries", "Shopping"):
            self.assertContains(self.client.get(list_url, {"start": "2026-05-01", "end": "2026-05-31", "category": self.cat[name].pk}), "SUPERSTORE")
        page = self.client.get(list_url, {"start": "2026-05-01", "end": "2026-05-31", "category": self.cat["Travel"].pk}).content.decode()
        self.assertNotIn(">SUPERSTORE<", page)
        csv = self.client.get(f"{list_url}export.csv", {"start": "2026-05-01", "end": "2026-05-31"}).content.decode()
        self.assertIn("Split: Groceries 30.00; Shopping 20.00", csv)

    def test_removing_a_split_restores_the_single_category(self):
        self.split(self.big, ("Groceries", "30.00"), ("Shopping", "20.00"))
        self.client.post(self.url(self.big), {"remove": "1"})
        self.assertFalse(SplitLine.objects.exists())
        self.assertEqual(self.totals()["Travel"], 5000)

    def test_only_the_account_owner_can_split(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.split(self.big, ("Groceries", "30.00"), ("Shopping", "20.00")).status_code, 404)
