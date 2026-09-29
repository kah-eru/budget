from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Budget, BudgetAlert, Category, Membership, Rule, SplitLine, Transaction, TransactionAnnotation, Workspace
from budget.rules import matches, suggest_keyword

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

    def test_the_picker_lists_every_visible_transaction_with_its_account_and_place(self, _):
        self.login(self.bob)
        page = self.client.get(self.url())
        names = [r.description for r in page.context["rows"]]
        self.assertIn("STAR TAILORS", names)  # the whole list, before any search
        self.assertNotIn("STARBUCKS private", names)  # not shared with the group
        self.assertContains(page, "Shared card (alice)")
        self.assertContains(page, "In Groceries")
        self.assertContains(page, "Uncategorized")
        self.assertFalse(any(r.ticked for r in page.context["rows"]))
        search = self.client.get(self.url(), {"q": "starbucks"})
        self.assertEqual({r.description: r.ticked for r in search.context["rows"]}, {"STARBUCKS #12": True, "Starbucks  Reserve": True, "STARBUCKS #88": False})
        self.assertNotIn("STARBUCKS #88", [r.description for r in self.client.get(self.url(), {"uncategorized": "on"}).context["rows"]])

    def test_a_row_in_another_category_asks_before_moving_and_forged_ids_are_ignored(self, _):
        self.login(self.bob)
        review = self.client.post(self.url(), {"ids": [self.sb1.pk, self.sb3.pk, self.secret.pk]})  # "also" off
        self.assertContains(review, "Move 1 transaction here?")
        self.assertContains(review, "1 in Groceries")
        self.assertIsNone(self.category_of(self.sb1))  # nothing saved until the answer
        self.client.post(self.url(), {"ids": [self.sb1.pk, self.sb3.pk], "review": "1", "move": "skip", "save": "1"})
        self.assertEqual((self.category_of(self.sb1), self.category_of(self.sb3)), ((self.dining, "manual"), (self.groceries, "manual")))
        self.client.post(self.url(), {"ids": [self.sb3.pk], "review": "1", "move": "move", "save": "1"})
        self.assertEqual(self.category_of(self.sb3), (self.dining, "manual"))
        self.assertFalse(TransactionAnnotation.objects.filter(transaction=self.secret, workspace=self.group).exists())
        # Nothing to ask: it saves straight away. Nothing ticked: back to the list.
        self.assertEqual(self.client.post(self.url(), {"ids": [self.tailor.pk]}).status_code, 302)
        self.assertEqual(self.client.post(self.url(), {"ids": [self.secret.pk]}).status_code, 400)

    def test_every_transaction_with_the_chosen_words_goes_here_now_and_later(self, _):
        Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=1000)
        self.login(self.bob)
        review = self.client.post(self.url(), {"ids": [self.sb1.pk], "also": "on"})
        self.assertEqual((review.context["offered"], review.context["words"]), (["STARBUCKS"], {"starbucks"}))  # "#12" is not a word to match
        self.assertEqual(review.context["matched"], 2)  # Reserve and #88; the private card stays out
        self.assertContains(review, "Move 1 transaction here?")  # #88 sits in Groceries
        self.assertEqual(self.client.post(self.url(), {"ids": [self.sb1.pk], "also": "on", "review": "1", "save": "1"}).status_code, 400)  # no words
        done = self.client.post(self.url(), {"ids": [self.sb1.pk], "also": "on", "review": "1", "words": ["STARBUCKS"], "move": "skip", "save": "1"})
        self.assertEqual(done.status_code, 302)
        self.assertEqual([self.category_of(r) for r in (self.sb1, self.sb2, self.sb3)], [(self.dining, "manual"), (self.dining, "manual"), (self.groceries, "manual")])
        self.assertEqual(list(Rule.objects.filter(category=self.dining).values_list("kind", "pattern")), [("words", "STARBUCKS")])
        self.client.post(self.url(), {"ids": [self.sb1.pk], "also": "on", "review": "1", "words": ["starbucks"], "move": "skip", "save": "1"})
        self.assertEqual(Rule.objects.filter(category=self.dining).count(), 1)  # the same words again: no second rule
        # A later transaction with those words lands here and counts toward the budget.
        self.login(self.alice)
        personal = Workspace.objects.get(owner=self.alice, is_personal=True)
        self.client.post(f"/workspaces/{personal.pk}/accounts/{self.card.pk}/transactions/new/",
                         {"posted_on": "2026-05-19", "amount": "6.00", "classification": "expense", "description": "STARBUCKS #300"})
        self.assertEqual(self.category_of(Transaction.objects.get(description="STARBUCKS #300")), (self.dining, "rule"))
        self.assertTrue(BudgetAlert.objects.filter(recipient=self.bob, silent=False).exists())  # $4.50 + $6.10 + $6.00 > $10

    def test_a_words_rule_needs_every_word_in_any_order(self, _):
        rule = Rule(kind="words", pattern="Starbucks  reserve")
        self.assertTrue(matches(rule, "RESERVE ROASTERY STARBUCKS #4"))
        self.assertFalse(matches(rule, "STARBUCKS #12"))

    def test_deleting_a_category_uncategorizes_and_removes_its_limits_and_rules(self, _):
        Budget.objects.create(workspace=self.group, category=self.groceries, limit_cents=1000)
        Rule.objects.create(workspace=self.group, pattern="tailor", category=self.groceries)
        for category in (self.groceries, self.dining):
            SplitLine.objects.create(transaction=self.tailor, workspace=self.group, category=category, amount_cents=1500)
        url = f"/workspaces/{self.group.pk}/categories/{self.groceries.pk}/delete/"
        self.login(self.eve)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.login(self.bob)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertRedirects(self.client.post(url), f"/workspaces/{self.group.pk}/budgets/", fetch_redirect_response=False)
        self.assertFalse(Category.objects.filter(pk=self.groceries.pk).exists())
        self.assertEqual(self.category_of(self.sb3), (None, ""))
        self.assertFalse(SplitLine.objects.filter(transaction=self.tailor).exists())  # the whole split, not half of it
        self.assertFalse(Budget.objects.filter(workspace=self.group).exists())
        self.assertFalse(Rule.objects.filter(workspace=self.group).exists())

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
