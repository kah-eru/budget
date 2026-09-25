from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from budget.models import Account, AccountShare, Membership, Transaction, Workspace
from budget.reporting import spending

JAN = (date(2026, 1, 1), date(2026, 1, 31))


class ReportingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        rows = [
            (10000, "expense", False, date(2026, 1, 5)),
            (2000, "expense", False, date(2026, 1, 10)),
            (1500, "refund", False, date(2026, 1, 12)),
            (10000, "transfer", False, date(2026, 1, 15)),  # card repayment
            (20000, "transfer", False, date(2026, 1, 16)),  # internal transfer
            (3000, "expense", True, date(2026, 1, 20)),
            (99900, "income", False, date(2026, 1, 1)),
            (700, "expense", False, date(2026, 2, 1)),  # boundary: February
        ]
        for cents, kind, pending, day in rows:
            Transaction.objects.create(account=cls.shared, amount_cents=cents, classification=kind, pending=pending, posted_on=day, description="Synthetic")
        Transaction.objects.create(account=cls.shared, amount_cents=400, classification="expense", posted_on=date(2026, 1, 31), description="Last day")
        Transaction.objects.create(account=cls.private, amount_cents=5000, classification="expense", posted_on=date(2026, 1, 8), description="Private")

    def test_fixture_totals_and_month_boundary(self):
        totals = spending(self.bob, self.group, *JAN)
        self.assertEqual(totals, {"posted_cents": 10900, "pending_cents": 3000, "income_cents": 99900})

    def test_february_boundary(self):
        self.assertEqual(spending(self.bob, self.group, date(2026, 2, 1), date(2026, 2, 28))["posted_cents"], 700)

    def test_personal_includes_private_but_group_omits_it(self):
        self.assertEqual(spending(self.alice, self.personal, *JAN)["posted_cents"], 15900)

    def test_unrelated_user_cannot_report_on_group(self):
        eve = get_user_model().objects.create_user("eve", password="synthetic-password")
        with self.assertRaises(Exception):
            spending(eve, self.group, *JAN)


class TransactionEntryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)

    def url(self, suffix="new/"):
        return f"/workspaces/{self.group.pk}/accounts/{self.shared.pk}/transactions/{suffix}"

    def post(self, user, amount="12.34", suffix="new/"):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        return self.client.post(self.url(suffix), {"posted_on": "2026-01-05", "amount": amount, "classification": "expense", "description": "Coffee"})

    def test_owner_adds_transaction_in_cents_and_bumps_group_revision(self):
        self.assertEqual(self.post(self.alice).status_code, 302)
        self.assertEqual(Transaction.objects.get().amount_cents, 1234)
        self.group.refresh_from_db()
        self.assertEqual(self.group.data_revision, 1)
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/accounts/{self.shared.pk}/"), "Coffee")

    def test_member_cannot_add_or_edit_anothers_transactions(self):
        self.assertEqual(self.post(self.bob).status_code, 404)
        row = Transaction.objects.create(account=self.shared, amount_cents=100, classification="expense", posted_on=date(2026, 1, 1))
        self.assertEqual(self.post(self.bob, suffix=f"{row.pk}/").status_code, 404)
        row.refresh_from_db()
        self.assertEqual(row.amount_cents, 100)

    def test_owner_edits_transaction(self):
        row = Transaction.objects.create(account=self.shared, amount_cents=100, classification="expense", posted_on=date(2026, 1, 1))
        self.assertEqual(self.post(self.alice, amount="2.50", suffix=f"{row.pk}/").status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.amount_cents, 250)

    def test_sub_cent_zero_and_negative_amounts_rejected(self):
        for amount in ("1.005", "0", "-5"):
            self.assertEqual(self.post(self.alice, amount=amount).status_code, 400)
        self.assertFalse(Transaction.objects.exists())


class DollarsFilterTests(TestCase):
    def test_formats_cents(self):
        from budget.templatetags.money import dollars
        self.assertEqual([dollars(c) for c in (0, 5, 123456, -150)], ["$0.00", "$0.05", "$1,234.56", "-$1.50"])


class AnnotationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.personal = Workspace.objects.get(owner=cls.alice, is_personal=True)
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared card")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        cls.row = Transaction.objects.create(account=cls.shared, amount_cents=5000, classification="expense", posted_on=date(2026, 1, 5), description="ACME 123")

    def annotate(self, user, workspace, **data):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        payload = {"display_name": "", "classification": "", "note": "", **data}
        return self.client.post(f"/workspaces/{workspace.pk}/accounts/{self.shared.pk}/transactions/{self.row.pk}/annotate/", payload)

    def test_personal_override_and_note_stay_out_of_group(self):
        self.assertEqual(self.annotate(self.alice, self.personal, display_name="Groceries run", classification="transfer", note="SECRET-NOTE").status_code, 302)
        self.assertEqual(spending(self.alice, self.personal, *JAN)["posted_cents"], 0)
        self.assertEqual(spending(self.bob, self.group, *JAN)["posted_cents"], 5000)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        page = self.client.get(f"/workspaces/{self.group.pk}/accounts/{self.shared.pk}/")
        self.assertContains(page, "ACME 123")
        self.assertNotContains(page, "SECRET-NOTE")
        self.assertNotContains(page, "Groceries run")

    def test_group_annotation_changes_group_total_and_preserves_source(self):
        self.assertEqual(self.annotate(self.alice, self.group, display_name="Groceries", classification="refund", note="Split later").status_code, 302)
        self.assertEqual(spending(self.bob, self.group, *JAN)["posted_cents"], -5000)
        self.assertEqual(spending(self.alice, self.personal, *JAN)["posted_cents"], 5000)
        self.row.refresh_from_db()
        self.assertEqual((self.row.description, self.row.classification, self.row.amount_cents), ("ACME 123", "expense", 5000))
        self.group.refresh_from_db()
        self.assertEqual(self.group.data_revision, 1)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/accounts/{self.shared.pk}/"), "Groceries")

    def test_blank_override_clears_and_member_cannot_annotate(self):
        self.annotate(self.alice, self.group, classification="transfer")
        self.annotate(self.alice, self.group, classification="")
        self.assertEqual(spending(self.bob, self.group, *JAN)["posted_cents"], 5000)
        self.assertEqual(self.annotate(self.bob, self.group, note="x").status_code, 404)


class YearlyTests(ReportingTests):
    def test_monthly_matches_spending_for_every_month_and_the_year(self):
        from budget.reporting import monthly
        months = monthly(self.bob, self.group, 2026)
        self.assertEqual(len(months), 12)
        self.assertEqual([m["posted_cents"] for m in months[:3]], [10900, 700, 0])
        year = spending(self.bob, self.group, date(2026, 1, 1), date(2026, 12, 31))
        for key in year:
            self.assertEqual(sum(m[key] for m in months), year[key])

    def test_workspace_period_views(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        year = self.client.get(f"/workspaces/{self.group.pk}/?period=2026")
        self.assertContains(year, "$116.00")  # 10900 + 700 posted over the year
        self.assertContains(year, "?period=2026-01\">January<")
        month = self.client.get(f"/workspaces/{self.group.pk}/?period=2026-02")
        self.assertContains(month, "February 2026")
        self.assertContains(month, "$7.00")
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/?period=nonsense").status_code, 200)


class TransactionListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob", "eve")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Alice card")
        cls.bobs = Account.objects.create(owner=cls.bob, name="Bob checking")
        cls.private = Account.objects.create(owner=cls.alice, name="Private card")
        for account in (cls.card, cls.bobs):
            AccountShare.objects.create(account=account, workspace=cls.group)
        cls.coffee = Transaction.objects.create(account=cls.card, amount_cents=450, posted_on=date(2026, 3, 2), description="BLUE BOTTLE 88")
        Transaction.objects.create(account=cls.bobs, amount_cents=9000, posted_on=date(2026, 3, 5), description="Hardware store")
        Transaction.objects.create(account=cls.private, amount_cents=100, posted_on=date(2026, 3, 3), description="Secret gift")
        from budget.models import TransactionAnnotation
        TransactionAnnotation.objects.create(transaction=cls.coffee, workspace=cls.group, display_name="Morning coffee")
        TransactionAnnotation.objects.create(transaction=cls.coffee, workspace=Workspace.objects.get(owner=cls.alice, is_personal=True), display_name="PERSONAL-NAME")

    def get(self, user, **params):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        return self.client.get(f"/workspaces/{self.group.pk}/transactions/", params)

    def test_lists_shared_rows_only(self):
        page = self.get(self.bob)
        self.assertContains(page, "Morning coffee")
        self.assertContains(page, "Hardware store")
        self.assertNotContains(page, "Secret gift")
        self.assertNotContains(page, "PERSONAL-NAME")

    def test_search_matches_original_and_group_name_but_not_personal_name(self):
        self.assertContains(self.get(self.bob, q="blue bottle"), "Morning coffee")
        self.assertContains(self.get(self.bob, q="morning"), "Morning coffee")
        self.assertNotContains(self.get(self.bob, q="PERSONAL-NAME"), "Morning coffee")
        self.assertNotContains(self.get(self.bob, q="secret"), "Secret gift")

    def test_account_person_and_date_filters(self):
        self.assertNotContains(self.get(self.bob, account=self.bobs.pk), "Morning coffee")
        self.assertNotContains(self.get(self.bob, person=self.bob.pk), "Morning coffee")
        self.assertContains(self.get(self.bob, person=self.alice.pk), "Morning coffee")
        dated = self.get(self.bob, start="2026-03-04", end="2026-03-31")
        self.assertContains(dated, "Hardware store")
        self.assertNotContains(dated, "Morning coffee")
        self.assertEqual(self.get(self.bob, start="2026-03-31", end="2026-03-01").status_code, 400)
        self.assertEqual(self.get(self.bob, account=self.private.pk).status_code, 400)

    def test_only_owner_rows_have_edit_links_and_outsider_gets_404(self):
        page = self.get(self.bob).content.decode()
        self.assertIn(f"/accounts/{self.bobs.pk}/transactions/", page)
        self.assertNotIn(f"/accounts/{self.card.pk}/transactions/", page)
        self.assertEqual(self.get(self.eve).status_code, 404)

    def test_cursor_pages_are_stable_and_query_count_is_constant(self):
        Transaction.objects.bulk_create(Transaction(account=self.card, amount_cents=100 + i, posted_on=date(2026, 1, 1), description=f"Same day {i}") for i in range(60))
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        url = f"/workspaces/{self.group.pk}/transactions/"
        with self.assertNumQueries(self.count_queries(url, {"q": "hardware"})):
            first = self.client.get(url)
        self.assertEqual(len(first.context["rows"]), 50)
        second = self.client.get(url + first.context["next_query"])
        seen = [r.pk for r in first.context["rows"]] + [r.pk for r in second.context["rows"]]
        self.assertEqual(len(seen), 62)
        self.assertEqual(len(set(seen)), 62)
        self.assertIsNone(second.context["next_query"])
        self.assertEqual(self.client.get(url, {"before": "garbage"}).status_code, 404)

    def count_queries(self, url, params):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.client.get(url, params)
        return len(ctx)

    def test_edit_returns_to_filtered_list_and_rejects_external_next(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        row = Transaction.objects.get(description="Hardware store")
        edit = f"/workspaces/{self.group.pk}/accounts/{self.bobs.pk}/transactions/{row.pk}/annotate/"
        back = f"/workspaces/{self.group.pk}/transactions/?q=hard"
        payload = {"display_name": "Tools", "classification": "", "note": ""}
        self.assertRedirects(self.client.post(edit + "?next=" + back.replace("?", "%3F").replace("=", "%3D"), payload), back, fetch_redirect_response=False)
        self.assertRedirects(self.client.post(edit + "?next=https://evil.example/", payload), f"/workspaces/{self.group.pk}/accounts/{self.bobs.pk}/", fetch_redirect_response=False)
