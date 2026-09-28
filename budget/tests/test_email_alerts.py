from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db.models.functions import Lower
from django.test import Client, TestCase

from budget.account_mail import unsubscribe_url
from budget.models import Account, AccountShare, Budget, Category, Membership, Transaction, TransactionAnnotation, Workspace
from budget.notifications import evaluate

TODAY = date(2026, 5, 20)


@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class EmailAlertTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.alice = User.objects.create_user("alice", email="alice@example.com", password="synthetic-password")
        cls.bob = User.objects.create_user("bob", email="bob@example.com", password="synthetic-password")
        User.objects.filter(pk__in=[cls.alice.pk, cls.bob.pk]).update(verified_email=Lower("email"))
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")
        cls.travel = Category.objects.get(workspace=cls.group, name="Travel")

    def login(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def turn(self, user, on):
        self.login(user)
        return self.client.post("/settings/email-alerts/", {"on": "1" if on else "0"})

    def cross(self, *categories):
        for category in categories or (self.dining,):
            Budget.objects.create(workspace=self.group, category=category, limit_cents=1000)
            row = Transaction.objects.create(account=self.card, amount_cents=1500, posted_on=TODAY, description="Cafe")
            TransactionAnnotation.objects.create(transaction=row, workspace=self.group, category=category, category_source="manual")
        with self.captureOnCommitCallbacks(execute=True):
            evaluate(self.group)

    def test_off_by_default(self, _):
        self.assertFalse(get_user_model().objects.get(pk=self.bob.pk).email_alerts)
        self.login(self.bob)
        self.assertContains(self.client.get("/settings/"), "Turn on email alerts")
        self.cross()
        self.assertEqual(mail.outbox, [])

    def test_one_generic_email_per_person_per_evaluation(self, _):
        self.turn(self.bob, True)
        self.assertContains(self.client.get("/settings/"), "Turn off email alerts")
        self.cross(self.dining, self.travel)  # two budgets cross at once: still one email
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["bob@example.com"])
        for private in ("Dining", "Travel", "15.00", "Cafe", "Partner group"):
            self.assertNotIn(private, message.body)
        self.assertIn("/alerts/", message.body)
        link = unsubscribe_url(self.bob)
        self.assertIn(link, message.body)
        self.assertEqual(message.extra_headers["List-Unsubscribe"], f"<{link}>")
        self.assertEqual(message.extra_headers["List-Unsubscribe-Post"], "List-Unsubscribe=One-Click")
        with self.captureOnCommitCallbacks(execute=True):
            evaluate(self.group)  # same period: already alerted
        self.assertEqual(len(mail.outbox), 1)

    def test_silent_baselines_never_email(self, _):
        self.turn(self.bob, True)
        with self.captureOnCommitCallbacks(execute=True):
            Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=1)
            Transaction.objects.create(account=self.card, amount_cents=1500, posted_on=TODAY, description="Cafe")
            evaluate(self.group, silent=True)
        self.assertEqual(mail.outbox, [])

    def test_needs_a_verified_email(self, _):
        get_user_model().objects.filter(pk=self.bob.pk).update(verified_email="")
        response = self.turn(self.bob, True)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.get(pk=self.bob.pk).email_alerts)
        self.assertContains(self.client.get("/settings/"), "Verify your email")

    def test_unsubscribe_link_needs_no_login_and_get_changes_nothing(self, _):
        self.turn(self.bob, True)
        client = Client(enforce_csrf_checks=True)  # mail apps post one-click unsubscribes without a CSRF token
        link = unsubscribe_url(self.bob)
        path = link[link.index("/email-alerts/"):]
        self.assertContains(client.get(path), "Turn off email alerts")
        self.assertTrue(get_user_model().objects.get(pk=self.bob.pk).email_alerts)
        self.assertEqual(client.post(path).status_code, 200)
        self.assertFalse(get_user_model().objects.get(pk=self.bob.pk).email_alerts)
        self.assertEqual(client.get("/email-alerts/unsubscribe/forged/").status_code, 404)
        self.assertEqual(client.post(path.replace(":", "x", 1)).status_code, 404)

    def test_turning_off_in_settings(self, _):
        self.turn(self.bob, True)
        self.turn(self.bob, False)
        self.cross()
        self.assertEqual(mail.outbox, [])

