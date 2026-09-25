from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Category, Membership, Transaction, TransactionAnnotation, Workspace
from budget.reporting import by_category, visible_transactions

MAY = (date(2026, 5, 1), date(2026, 5, 31))


class CategoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        cls.groceries = Category.objects.get(workspace=cls.group, name="Groceries")
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")
        make = Transaction.objects.create
        cls.shop = make(account=cls.shared, amount_cents=5000, posted_on=date(2026, 5, 2), description="MARKET")
        cls.refund = make(account=cls.shared, amount_cents=500, classification="refund", posted_on=date(2026, 5, 3), description="MARKET REFUND")
        cls.cafe = make(account=cls.shared, amount_cents=1200, posted_on=date(2026, 5, 4), description="CAFE")
        cls.misc = make(account=cls.shared, amount_cents=700, posted_on=date(2026, 5, 5), description="MISC")
        make(account=cls.shared, amount_cents=9000, classification="transfer", posted_on=date(2026, 5, 6), description="CARD PAYMENT")
        cls.secret = make(account=cls.private, amount_cents=3333, posted_on=date(2026, 5, 7), description="PRIVATE")
        for row, category in ((cls.shop, cls.groceries), (cls.refund, cls.groceries), (cls.cafe, cls.dining)):
            TransactionAnnotation.objects.create(transaction=row, workspace=cls.group, category=category)

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def test_every_new_workspace_starts_with_standard_categories(self):
        personal = Workspace.objects.get(owner=self.eve, is_personal=True)
        names = set(Category.objects.filter(workspace=personal).values_list("name", flat=True))
        self.assertIn("Groceries", names)
        self.assertEqual(names, set(Category.objects.filter(workspace=self.group).values_list("name", flat=True)))

    def test_by_category_nets_refunds_skips_transfers_and_private_accounts(self):
        totals = {t["name"]: t["posted_cents"] for t in by_category(visible_transactions(self.bob, self.group), *MAY)}
        self.assertEqual(totals, {"Groceries": 4500, "Dining": 1200, "Uncategorized": 700})
        self.assertEqual(list(totals), ["Groceries", "Dining", "Uncategorized"])  # largest first

    def test_overview_lists_category_spending(self):
        self.login(self.bob)
        page = self.client.get(f"/workspaces/{self.group.pk}/", {"period": "2026-05"}).content.decode()
        self.assertIn("Groceries", page)
        self.assertIn("$45.00", page)
        self.assertNotIn("$33.33", page)

    def test_timeline_filters_by_category_and_uncategorized(self):
        self.login(self.bob)
        url = f"/workspaces/{self.group.pk}/transactions/"
        page = self.client.get(url, {"start": "2026-05-01", "end": "2026-05-31", "category": self.groceries.pk}).content.decode()
        self.assertIn("MARKET REFUND", page)
        self.assertNotIn("CAFE", page)
        page = self.client.get(url, {"start": "2026-05-01", "end": "2026-05-31", "category": "none"}).content.decode()
        self.assertIn("MISC", page)
        self.assertNotIn("CAFE", page)

    def test_annotation_offers_only_this_workspaces_active_categories(self):
        self.login(self.alice)
        personal_groceries = Category.objects.get(workspace__owner=self.alice, workspace__is_personal=True, name="Groceries")
        url = f"/workspaces/{self.group.pk}/accounts/{self.shared.pk}/transactions/{self.misc.pk}/annotate/"
        response = self.client.post(url, {"category": personal_groceries.pk})
        self.assertEqual(response.status_code, 400)
        self.dining.archived = True
        self.dining.save()
        self.assertNotContains(self.client.get(url), ">Dining<")
        self.client.post(url, {"category": self.groceries.pk})
        self.assertEqual(TransactionAnnotation.objects.get(transaction=self.misc, workspace=self.group).category, self.groceries)

    def test_members_manage_categories_names_are_unique_and_archive_keeps_history(self):
        self.login(self.bob)
        url = f"/workspaces/{self.group.pk}/categories/"
        self.assertEqual(self.client.post(url, {"name": "  pets "}).status_code, 302)
        self.assertTrue(Category.objects.filter(workspace=self.group, name="pets").exists())
        self.assertEqual(self.client.post(url, {"name": "GROCERIES"}).status_code, 400)
        edit = f"{url}{self.dining.pk}/"
        self.client.post(edit, {"name": "Eating out", "archived": "on"})
        self.dining.refresh_from_db()
        self.assertEqual((self.dining.name, self.dining.archived), ("Eating out", True))
        self.assertEqual(TransactionAnnotation.objects.get(transaction=self.cafe, workspace=self.group).category, self.dining)

    def test_categorized_history_blocks_category_delete_but_not_workspace_delete(self):
        from django.db.models import RestrictedError
        with self.assertRaises(RestrictedError):
            self.dining.delete()
        self.group.delete()
        self.assertFalse(Category.objects.filter(workspace_id=self.group.pk).exists())

    def test_outsiders_cannot_see_or_edit_categories(self):
        self.login(self.eve)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/categories/").status_code, 404)
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/categories/{self.dining.pk}/", {"name": "x"}).status_code, 404)

    def test_csv_export_includes_category(self):
        self.login(self.bob)
        body = self.client.get(f"/workspaces/{self.group.pk}/transactions/export.csv", {"start": "2026-05-01", "end": "2026-05-31"}).content.decode()
        self.assertIn("Category", body.splitlines()[0])
        self.assertIn("Dining", body)
