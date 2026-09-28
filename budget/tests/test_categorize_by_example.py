from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, BudgetAlert, Category, Membership, Rule, Transaction, TransactionAnnotation, Workspace
from budget.rules import suggest_keyword

TODAY = date(2026, 5, 20)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class CategorizeByExampleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Shared card")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")
        cls.groceries = Category.objects.get(workspace=cls.group, name="Groceries")
        make = Transaction.objects.create
        cls.sb1 = make(account=cls.card, amount_cents=450, posted_on=date(2026, 5, 2), description="STARBUCKS #12")
        cls.sb2 = make(account=cls.card, amount_cents=610, posted_on=date(2026, 5, 3), description="Starbucks  Reserve")
        cls.sb3 = make(account=cls.card, amount_cents=300, posted_on=date(2026, 5, 4), description="STARBUCKS #88")
        cls.tailor = make(account=cls.card, amount_cents=3000, posted_on=date(2026, 5, 5), description="STAR TAILORS")
        cls.secret = make(account=cls.private, amount_cents=999, posted_on=date(2026, 5, 6), description="STARBUCKS private")
        TransactionAnnotation.objects.create(transaction=cls.sb3, workspace=cls.group, category=cls.groceries, category_source="manual")

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def url(self):
        return f"/workspaces/{self.group.pk}/categories/{self.dining.pk}/add/"

    def category_of(self, row):
        ann = TransactionAnnotation.objects.filter(transaction=row, workspace=self.group).first()
        return ann and (ann.category, ann.category_source)

    def test_search_lists_visible_matches_and_flags_hand_set_rows(self, _):
        self.login(self.bob)
        page = self.client.get(self.url(), {"q": "starbucks"}).content.decode()
        self.assertIn("STARBUCKS #12", page)
        self.assertIn("Starbucks  Reserve", page)
        self.assertIn("Set by hand: Groceries", page)
        self.assertNotIn("STAR TAILORS", page)
        self.assertNotIn("private", page)

    def test_ticked_rows_become_manual_forged_ids_are_ignored_and_rule_is_created_once(self, _):
        self.login(self.bob)
        data = {"q": "starbucks", "keyword": "starbucks", "ids": [self.sb1.pk, self.secret.pk, self.tailor.pk], "make_rule": "on"}
        self.assertEqual(self.client.post(self.url(), data).status_code, 302)
        self.assertEqual(self.category_of(self.sb1), (self.dining, "manual"))
        self.assertIsNone(self.category_of(self.sb2))  # unticked: unchanged, no backfill
        self.assertIsNone(self.category_of(self.tailor))  # does not match the search
        self.assertFalse(TransactionAnnotation.objects.filter(transaction=self.secret, workspace=self.group).exists())
        self.client.post(self.url(), {**data, "keyword": "  STARBUCKS "})
        self.assertEqual(Rule.objects.filter(workspace=self.group, category=self.dining).count(), 1)

    def test_future_matches_count_toward_the_category_budget_and_alert(self, _):
        Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=1000)
        self.login(self.bob)
        self.client.post(self.url(), {"q": "starbucks", "keyword": "starbucks", "ids": [self.sb1.pk], "make_rule": "on"})
        self.login(self.alice)
        personal = Workspace.objects.get(owner=self.alice, is_personal=True)
        self.client.post(f"/workspaces/{personal.pk}/accounts/{self.card.pk}/transactions/new/",
                         {"posted_on": "2026-05-19", "amount": "6.00", "classification": "expense", "description": "STARBUCKS #300"})
        new = Transaction.objects.get(description="STARBUCKS #300")
        self.assertEqual(self.category_of(new), (self.dining, "rule"))
        self.assertTrue(BudgetAlert.objects.filter(recipient=self.bob, silent=False).exists())  # $4.50 + $6.00 > $10

    def test_suggested_keyword_drops_store_numbers(self, _):
        self.assertEqual(suggest_keyword("STARBUCKS #12 SEATTLE WA 98101"), "STARBUCKS SEATTLE WA")
        self.assertEqual(suggest_keyword("  Fresh   Market "), "Fresh Market")
        self.assertEqual(suggest_keyword("12345"), "")
        self.assertEqual(suggest_keyword("7-ELEVEN #123"), "7-ELEVEN")

    def test_one_transaction_also_applies_to_similar_non_manual_rows(self, _):
        self.login(self.alice)
        url = f"/workspaces/{self.group.pk}/accounts/{self.card.pk}/transactions/{self.sb1.pk}/annotate/"
        self.assertContains(self.client.get(url), 'value="STARBUCKS"')
        self.client.post(url, {"category": self.dining.pk, "also_similar": "on", "match_text": "starbucks"})
        self.assertEqual(self.category_of(self.sb1), (self.dining, "manual"))
        self.assertEqual(self.category_of(self.sb2), (self.dining, "rule"))
        self.assertEqual(self.category_of(self.sb3), (self.groceries, "manual"))  # hand-set stays
        self.assertIsNone(self.category_of(self.tailor))
        self.assertEqual(self.client.post(url, {"also_similar": "on", "match_text": "starbucks"}).status_code, 400)  # needs a category

    def test_outsiders_get_404(self, _):
        self.login(self.eve)
        self.assertEqual(self.client.get(self.url(), {"q": "starbucks"}).status_code, 404)
        self.assertEqual(self.client.post(self.url(), {"q": "starbucks", "ids": [self.sb1.pk]}).status_code, 404)
