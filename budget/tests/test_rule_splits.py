from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, Category, Rule, SplitLine, Transaction, Workspace
from budget.reporting import by_category, visible_transactions
from budget.rules import categorize, largest_remainder

MAY = (date(2026, 5, 1), date(2026, 5, 31))


class RuleSplitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")
        cls.ws = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.card = Account.objects.create(owner=cls.alice, name="Card")
        cls.cat = {c.name: c for c in Category.objects.filter(workspace=cls.ws)}
        cls.costco = Transaction.objects.create(account=cls.card, amount_cents=1001, posted_on=date(2026, 5, 2), description="COSTCO WHSE #4")

    def rule(self, **kw):
        return Rule.objects.create(workspace=self.ws, pattern="costco", category=self.cat["Groceries"], **kw)

    def lines(self):
        return {l.category.name: (l.amount_cents, l.from_rule) for l in SplitLine.objects.filter(transaction=self.costco, workspace=self.ws)}

    def test_largest_remainder_always_adds_up(self):
        self.assertEqual(largest_remainder(1001, [70, 30]), [701, 300])
        self.assertEqual(largest_remainder(1, [50, 50]), [1, 0])
        self.assertEqual(largest_remainder(1000, [33, 67]), [330, 670])
        for total in range(1, 400):
            self.assertEqual(sum(largest_remainder(total, [70, 30])), total)

    def test_split_rule_creates_lines_that_reports_count(self):
        self.rule(split_category=self.cat["Shopping"], split_percent=30)
        categorize([self.costco], self.ws)
        self.assertEqual(self.lines(), {"Groceries": (701, True), "Shopping": (300, True)})
        totals = {t["name"]: t["posted_cents"] for t in by_category(visible_transactions(self.alice, self.ws), *MAY, self.ws)}
        self.assertEqual(totals, {"Groceries": 701, "Shopping": 300})

    def test_changing_the_rule_replaces_rule_lines_but_never_hand_made_splits(self):
        rule = self.rule(split_category=self.cat["Shopping"], split_percent=30)
        categorize([self.costco], self.ws)
        rule.split_category, rule.split_percent = None, None
        rule.save()
        categorize([self.costco], self.ws)
        self.assertEqual(self.lines(), {})
        SplitLine.objects.bulk_create([SplitLine(transaction=self.costco, workspace=self.ws, category=self.cat["Health"], amount_cents=500),
                                       SplitLine(transaction=self.costco, workspace=self.ws, category=self.cat["Travel"], amount_cents=501)])
        rule.split_category, rule.split_percent = self.cat["Shopping"], 50
        rule.save()
        categorize([self.costco], self.ws)
        self.assertEqual(self.lines(), {"Health": (500, False), "Travel": (501, False)})

    def test_picking_a_category_by_hand_drops_the_rule_split(self):
        self.rule(split_category=self.cat["Shopping"], split_percent=30)
        categorize([self.costco], self.ws)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.client.post(f"/workspaces/{self.ws.pk}/accounts/{self.card.pk}/transactions/{self.costco.pk}/annotate/", {"category": self.cat["Health"].pk})
        self.assertEqual(self.lines(), {})
        categorize([self.costco], self.ws)  # manual now: the rule leaves it alone
        self.assertEqual(self.lines(), {})

    def test_form_validates_the_split_and_archiving_disables_it(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.ws.pk}/rules/new/"
        base = {"kind": "contains", "pattern": "costco", "category": self.cat["Groceries"].pk, "priority": 100, "enabled": "on"}
        self.assertEqual(self.client.post(url, {**base, "split_category": self.cat["Groceries"].pk, "split_percent": 30}).status_code, 400)
        self.assertEqual(self.client.post(url, {**base, "split_category": self.cat["Shopping"].pk, "split_percent": 100}).status_code, 400)
        self.assertEqual(self.client.post(url, {**base, "split_category": self.cat["Shopping"].pk}).status_code, 400)
        self.assertEqual(self.client.post(url, {**base, "split_category": self.cat["Shopping"].pk, "split_percent": 30, "apply_existing": "on"}).status_code, 302)
        self.assertEqual(self.lines(), {"Groceries": (701, True), "Shopping": (300, True)})
        self.client.post(f"/workspaces/{self.ws.pk}/categories/{self.cat['Shopping'].pk}/", {"name": "Shopping", "archived": "on"})
        self.assertFalse(Rule.objects.get().enabled)
