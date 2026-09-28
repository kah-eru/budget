import csv
import io
from datetime import date
from unittest import mock

from django.core import mail, signing
from django.test import TestCase

from budget.models import Account, AccountShare, Membership, Transaction, TransactionAnnotation, User, Workspace

PASSWORD = "synthetic-password"


def login(client, user):
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")


class SettingsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", email="alice@example.com", password=PASSWORD)
        self.user.verified_email = "alice@example.com"
        self.user.save()

    def test_needs_login_lists_actions_and_old_url_redirects(self):
        self.assertEqual(self.client.get("/settings/").status_code, 302)
        login(self.client, self.user)
        page = self.client.get("/settings/")
        for text in ("Change username", "Change email", "Change password", "Appearance", "Export transactions", "Sign out", "Add account", "alice@example.com"):
            self.assertContains(page, text)
        self.assertRedirects(self.client.get("/more/"), "/settings/")

    def test_username_change_needs_password_and_notifies(self):
        login(self.client, self.user)
        self.assertEqual(self.client.post("/settings/username/", {"username": "alice2", "current_password": "wrong"}).status_code, 400)
        self.assertEqual(self.client.post("/settings/username/", {"username": "alice2", "current_password": PASSWORD}).status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "alice2")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alice@example.com"])
        self.assertIn("alice2", mail.outbox[0].body)

    def test_username_taken_is_rejected(self):
        User.objects.create_user("bob", password=PASSWORD)
        login(self.client, self.user)
        self.assertEqual(self.client.post("/settings/username/", {"username": "bob", "current_password": PASSWORD}).status_code, 400)

    def test_no_notice_without_verified_email(self):
        self.user.verified_email = ""
        self.user.save()
        login(self.client, self.user)
        self.client.post("/settings/username/", {"username": "alice2", "current_password": PASSWORD})
        self.assertEqual(mail.outbox, [])

    def test_mail_failure_does_not_fail_a_completed_change(self):
        login(self.client, self.user)
        with mock.patch("budget.account_mail.send_mail", side_effect=OSError):
            self.assertEqual(self.client.post("/settings/username/", {"username": "alice2", "current_password": PASSWORD}).status_code, 302)

    def test_password_change_notifies(self):
        login(self.client, self.user)
        new = "Another-long-synthetic-passphrase-19"
        self.client.post("/settings/password/", {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password", mail.outbox[0].subject.lower())


class EmailChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("alice", email="alice@example.com", password=PASSWORD)
        self.user.verified_email = "alice@example.com"
        self.user.save()
        login(self.client, self.user)

    def request_change(self, email="New@Example.com"):
        return self.client.post("/settings/email/", {"email": email, "current_password": PASSWORD})

    def link(self):
        body = next(m.body for m in mail.outbox if m.to == ["new@example.com"])
        return next(line for line in body.splitlines() if "/settings/email/" in line).split("testserver")[1]

    def test_link_goes_to_new_address_and_notice_to_old(self):
        self.assertEqual(self.request_change().status_code, 302)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["alice@example.com", "new@example.com"])
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")  # nothing changes before the link is opened
        link = self.link()
        self.assertEqual(self.client.get(link).status_code, 200)
        self.assertEqual(self.client.post(link).status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual((self.user.email, self.user.verified_email), ("new@example.com", "new@example.com"))

    def test_wrong_password_same_email_and_taken_email_are_rejected(self):
        User.objects.create_user("bob", email="bob@example.com", password=PASSWORD)
        self.assertEqual(self.client.post("/settings/email/", {"email": "new@example.com", "current_password": "wrong"}).status_code, 400)
        self.assertEqual(self.request_change("ALICE@example.com").status_code, 400)
        self.assertEqual(self.request_change("bob@example.com").status_code, 400)
        self.assertEqual(mail.outbox, [])

    def test_rate_limited(self):
        self.request_change()
        self.assertEqual(self.request_change("other@example.com").status_code, 400)

    def test_other_user_token_is_404(self):
        self.request_change()
        link = self.link()
        login(self.client, User.objects.create_user("bob", password=PASSWORD))
        self.assertEqual(self.client.post(link).status_code, 404)

    def test_password_change_or_bad_token_invalidates_link(self):
        self.request_change()
        link = self.link()
        self.user.set_password("Another-long-synthetic-passphrase-19")
        self.user.save()
        login(self.client, self.user)
        self.assertEqual(self.client.post(link).status_code, 400)
        self.assertEqual(self.client.post("/settings/email/garbage/").status_code, 400)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "alice@example.com")

    def test_expired_link(self):
        self.request_change()
        link = self.link()
        with mock.patch("budget.views.EMAIL_CHANGE_MAX_AGE", -1):
            self.assertEqual(self.client.post(link).status_code, 400)

    def test_email_taken_meanwhile_is_an_error_not_500(self):
        self.request_change()
        link = self.link()
        User.objects.create_user("bob", email="new@example.com", password=PASSWORD)
        self.assertEqual(self.client.post(link).status_code, 400)


class ExportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [User.objects.create_user(n, password=PASSWORD) for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        shared = Account.objects.create(owner=cls.alice, name="Shared card")
        private = Account.objects.create(owner=cls.alice, name="Private card")
        AccountShare.objects.create(account=shared, workspace=cls.group)
        make = Transaction.objects.create
        cls.coffee = make(account=shared, amount_cents=450, posted_on=date(2026, 5, 1), description="=HYPERLINK(evil)")
        make(account=shared, amount_cents=1500, classification="refund", pending=True, posted_on=date(2026, 5, 3), description="Refund")
        make(account=private, amount_cents=999, posted_on=date(2026, 5, 2), description="Private")
        TransactionAnnotation.objects.create(transaction=cls.coffee, workspace=cls.group, display_name="Coffee", note="Group note")

    def export(self, **params):
        login(self.client, self.bob)
        return self.client.get(f"/workspaces/{self.group.pk}/transactions/export.csv", {"start": "2026-05-01", "end": "2026-05-31", **params})

    def rows(self, response):
        return list(csv.reader(io.StringIO(response.content.decode())))

    def test_group_export_matches_timeline_and_hides_private(self):
        response = self.export()
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn('attachment; filename="budget-2026-05-01-2026-05-31.csv"', response["Content-Disposition"])
        self.assertIn("no-store", response["Cache-Control"])
        header, *rows = self.rows(response)
        self.assertEqual(header, ["Date", "Account", "Owner", "Name", "Original description", "Category", "Classification", "Status", "Amount (USD)", "Note"])
        self.assertEqual(rows, [
            ["2026-05-03", "Shared card", "alice", "Refund", "Refund", "", "Refund", "Pending", "15.00", ""],
            ["2026-05-01", "Shared card", "alice", "Coffee", "'=HYPERLINK(evil)", "", "Expense", "Posted", "4.50", "Group note"],
        ])

    def test_filters_apply(self):
        self.assertEqual(len(self.rows(self.export(q="coffee"))), 2)

    def test_bad_range_and_login(self):
        self.assertEqual(self.export(start="2020-01-01").status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/transactions/export.csv").status_code, 302)
