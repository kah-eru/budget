from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from budget.models import Account, AccountShare, Membership, Transaction, Workspace
from budget.reporting import daily, spending, visible_transactions
from budget.sharing import bump_account_data

MAY = (date(2026, 5, 1), date(2026, 5, 3))


class TimelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        make = Transaction.objects.create
        make(account=cls.shared, amount_cents=10000, posted_on=date(2026, 5, 1), description="Day one")
        make(account=cls.shared, amount_cents=300, pending=True, posted_on=date(2026, 5, 2), description="Pending")
        make(account=cls.shared, amount_cents=1500, classification="refund", posted_on=date(2026, 5, 3), description="Refund")
        make(account=cls.private, amount_cents=999, posted_on=date(2026, 5, 2), description="Private")

    def get(self, **params):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        return self.client.get(f"/workspaces/{self.group.pk}/transactions/", params)

    def test_daily_and_cumulative_match_plan_fixture_and_spending(self):
        days = daily(visible_transactions(self.bob, self.group), *MAY)
        self.assertEqual([d["posted_cents"] for d in days], [10000, 0, -1500])
        self.assertEqual([d["cumulative_cents"] for d in days], [10000, 10000, 8500])
        self.assertEqual([d["pending_cents"] for d in days], [0, 300, 0])
        total = spending(self.bob, self.group, *MAY)
        self.assertEqual(sum(d["posted_cents"] for d in days), total["posted_cents"])
        self.assertEqual(sum(d["pending_cents"] for d in days), total["pending_cents"])

    def test_page_shows_daily_table_and_excludes_private(self):
        page = self.get(start="2026-05-01", end="2026-05-03")
        self.assertEqual([d["cumulative_cents"] for d in page.context["days"]], [10000, 10000, 8500])
        self.assertContains(page, "$85.00")
        self.assertNotContains(page, "Private")

    def test_default_range_and_two_year_cap(self):
        today = timezone.localdate()
        page = self.get()
        self.assertEqual((page.context["start"], page.context["end"]), (today.replace(day=1), today))
        only_end = self.get(end="2026-05-20")
        self.assertEqual(only_end.context["start"], date(2026, 5, 1))
        only_start = self.get(start="2026-05-20")
        self.assertEqual(only_start.context["end"], date(2026, 5, 31))
        self.assertEqual(self.get(start="2024-01-01", end="2026-01-02").status_code, 400)

    def test_cursor_restarts_when_workspace_data_changes(self):
        Transaction.objects.bulk_create(Transaction(account=self.shared, amount_cents=100, posted_on=date(2026, 5, 2), description=f"Bulk {i}") for i in range(60))
        first = self.get(start="2026-05-01", end="2026-05-31")
        next_query = first.context["next_query"]
        self.assertIn("rev=", next_query)
        newest = Transaction.objects.create(account=self.shared, amount_cents=5, posted_on=date(2026, 5, 31), description="Newest")
        bump_account_data(self.shared)
        stale = self.client.get(f"/workspaces/{self.group.pk}/transactions/" + next_query)
        self.assertTrue(stale.context["stale"])
        self.assertEqual(stale.context["rows"][0].pk, newest.pk)
        self.assertContains(stale, "This list changed since you loaded it")
