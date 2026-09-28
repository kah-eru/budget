from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Category, Membership, Rule, Transaction, TransactionAnnotation, Workspace
from budget.rules import categorize, matches


class RuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        cls.other = Workspace.objects.create(owner=cls.alice, name="Other group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")
        cls.groceries = Category.objects.get(workspace=cls.group, name="Groceries")
        cls.coffee = Transaction.objects.create(account=cls.card, amount_cents=450, posted_on=date(2026, 5, 2), description="  STARBUCKS   #12 ")
        cls.market = Transaction.objects.create(account=cls.card, amount_cents=5000, posted_on=date(2026, 5, 3), description="Fresh Market")

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def category_of(self, row, workspace=None):
        ann = TransactionAnnotation.objects.filter(transaction=row, workspace=workspace or self.group).first()
        return ann and ann.category

    def test_matching_normalizes_whitespace_and_case(self):
        self.assertTrue(matches(Rule(kind="contains", pattern="starbucks"), self.coffee.description))
        self.assertTrue(matches(Rule(kind="exact", pattern="Starbucks #12"), self.coffee.description))
        self.assertFalse(matches(Rule(kind="exact", pattern="Starbucks"), self.coffee.description))
        self.assertTrue(matches(Rule(kind="contains", pattern="STRASSE"), "Café Straße"))

    def test_priority_then_rule_id_decides_and_manual_choice_is_kept(self):
        Rule.objects.create(workspace=self.group, pattern="market", category=self.dining, priority=5)
        Rule.objects.create(workspace=self.group, pattern="fresh", category=self.groceries, priority=5)
        Rule.objects.create(workspace=self.group, pattern="star", category=self.groceries, priority=1)
        Rule.objects.create(workspace=self.group, pattern="starbucks", category=self.dining, priority=2)
        categorize([self.coffee, self.market], self.group)
        self.assertEqual(self.category_of(self.coffee), self.groceries)
        self.assertEqual(self.category_of(self.market), self.dining)  # equal priority: the older rule
        TransactionAnnotation.objects.filter(transaction=self.market, workspace=self.group).update(category=None, category_source="manual")
        categorize([self.market], self.group)
        self.assertIsNone(self.category_of(self.market))

    def test_new_and_edited_transactions_use_each_workspaces_rules(self):
        Rule.objects.create(workspace=self.group, pattern="bakery", category=self.dining)
        Rule.objects.create(workspace=self.personal, pattern="bakery", category=Category.objects.get(workspace=self.personal, name="Groceries"))
        Rule.objects.create(workspace=self.other, pattern="bakery", category=Category.objects.get(workspace=self.other, name="Travel"))
        self.login(self.alice)
        self.client.post(f"/workspaces/{self.personal.pk}/accounts/{self.card.pk}/transactions/new/",
                         {"posted_on": "2026-05-04", "amount": "7.25", "classification": "expense", "description": "Corner Bakery"})
        row = Transaction.objects.get(description="Corner Bakery")
        self.assertEqual(self.category_of(row), self.dining)
        self.assertEqual(self.category_of(row, self.personal).name, "Groceries")
        self.assertIsNone(self.category_of(row, self.other))  # not shared there
        self.client.post(f"/workspaces/{self.personal.pk}/accounts/{self.card.pk}/transactions/{row.pk}/",
                         {"posted_on": "2026-05-04", "amount": "7.25", "classification": "expense", "description": "Hardware store"})
        self.assertIsNone(self.category_of(row))

    def test_preview_saves_nothing_and_backfill_is_opt_in(self):
        self.login(self.bob)
        url = f"/workspaces/{self.group.pk}/rules/new/"
        data = {"kind": "contains", "pattern": "starbucks", "category": self.dining.pk, "priority": 100, "enabled": "on"}
        page = self.client.post(url, {**data, "preview": "1"}).content.decode()
        self.assertIn("STARBUCKS", page)
        self.assertFalse(Rule.objects.exists())
        self.client.post(url, data)
        self.assertIsNone(self.category_of(self.coffee))
        rule = Rule.objects.get()
        self.client.post(f"/workspaces/{self.group.pk}/rules/{rule.pk}/", {**data, "apply_existing": "on"})
        self.assertEqual(self.category_of(self.coffee), self.dining)

    def test_archiving_a_category_disables_its_rules(self):
        rule = Rule.objects.create(workspace=self.group, pattern="starbucks", category=self.dining)
        self.login(self.bob)
        self.client.post(f"/workspaces/{self.group.pk}/categories/{self.dining.pk}/", {"name": "Dining", "archived": "on"})
        rule.refresh_from_db()
        self.assertFalse(rule.enabled)

    def test_rejects_blank_patterns_foreign_categories_and_outsiders(self):
        self.login(self.bob)
        url = f"/workspaces/{self.group.pk}/rules/new/"
        self.assertEqual(self.client.post(url, {"kind": "contains", "pattern": "   ", "category": self.dining.pk, "priority": 1}).status_code, 400)
        foreign = Category.objects.get(workspace=self.personal, name="Dining")
        self.assertEqual(self.client.post(url, {"kind": "contains", "pattern": "x", "category": foreign.pk, "priority": 1}).status_code, 400)
        self.login(self.eve)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/rules/").status_code, 404)
