import json
from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from budget.models import Account, AccountShare, Budget, Category, Membership, PushSubscription, Transaction, TransactionAnnotation, Workspace
from budget.notifications import evaluate

TODAY = date(2026, 5, 20)
KEYS = {"WEBPUSH_VAPID_PUBLIC_KEY": "synthetic-public", "WEBPUSH_VAPID_PRIVATE_KEY": "synthetic-private"}
ENDPOINT = "https://fcm.googleapis.com/fcm/send/synthetic-device"


@override_settings(**KEYS)
@mock.patch("django.utils.timezone.localdate", return_value=TODAY)
class PushTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.card = Account.objects.create(owner=cls.alice, name="Card")
        AccountShare.objects.create(account=cls.card, workspace=cls.group)
        cls.dining = Category.objects.get(workspace=cls.group, name="Dining")

    def subscribe(self, user, endpoint=ENDPOINT, **extra):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
        body = {"endpoint": endpoint, "keys": {"p256dh": "synthetic-p256dh", "auth": "synthetic-auth"}, **extra}
        return self.client.post("/push/subscribe/", json.dumps(body), content_type="application/json")

    def cross(self):
        budget = Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=1000)
        row = Transaction.objects.create(account=self.card, amount_cents=1500, posted_on=TODAY, description="Cafe")
        TransactionAnnotation.objects.create(transaction=row, workspace=self.group, category=self.dining, category_source="manual")
        with self.captureOnCommitCallbacks(execute=True):
            evaluate(self.group)
        return budget

    def test_subscribe_validates_the_push_service_and_unsubscribe_is_per_user(self, _):
        self.assertEqual(self.subscribe(self.bob).status_code, 204)
        self.assertEqual(self.subscribe(self.bob, endpoint="http://fcm.googleapis.com/x").status_code, 400)
        self.assertEqual(self.subscribe(self.bob, endpoint="https://169.254.169.254/latest").status_code, 400)
        self.assertEqual(self.subscribe(self.bob, endpoint="https://evil.example/fcm.googleapis.com").status_code, 400)
        self.assertEqual(self.subscribe(self.bob, keys={}).status_code, 400)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.client.post("/push/unsubscribe/", json.dumps({"endpoint": ENDPOINT}), content_type="application/json")
        self.assertTrue(PushSubscription.objects.filter(user=self.bob).exists())  # not alice's to remove
        self.client.logout()
        self.assertEqual(self.client.post("/push/subscribe/", "{}", content_type="application/json").status_code, 302)

    @mock.patch("budget.push.webpush")
    def test_a_new_crossing_pushes_generic_text_once_per_device(self, webpush, _):
        self.subscribe(self.bob)
        self.cross()
        webpush.assert_called_once()
        payload = json.loads(webpush.call_args.kwargs["data"])
        self.assertEqual(payload, {"title": "Budget alert", "body": "A budget went over its limit. Open Budget to see which one.", "url": "/alerts/"})
        with self.captureOnCommitCallbacks(execute=True):
            evaluate(self.group)  # same period: already alerted
        webpush.assert_called_once()

    @mock.patch("budget.push.webpush")
    def test_silent_baselines_never_push_and_gone_devices_are_removed(self, webpush, _):
        from pywebpush import WebPushException
        self.subscribe(self.bob)
        self.cross()
        webpush.reset_mock()
        with self.captureOnCommitCallbacks(execute=True):
            evaluate(self.group, silent=True, budgets=[Budget.objects.create(workspace=self.group, category=self.dining, limit_cents=100)])
        webpush.assert_not_called()
        webpush.side_effect = WebPushException("gone", response=mock.Mock(status_code=410))
        Budget.objects.all().delete()
        self.cross()
        self.assertFalse(PushSubscription.objects.exists())

    def test_service_worker_only_handles_push(self, _):
        response = self.client.get("/sw.js")
        self.assertEqual(response["Content-Type"], "application/javascript")
        body = response.content.decode()
        self.assertIn("push", body)
        self.assertNotIn('addEventListener("fetch"', body)  # never caches or intercepts financial pages

    @mock.patch("budget.push.webpush")
    def test_push_is_off_without_keys(self, webpush, _):
        self.subscribe(self.bob)
        with override_settings(WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY=""):
            self.cross()
            self.assertNotContains(self.client.get("/settings/"), "data-push")
        webpush.assert_not_called()
        self.assertContains(self.client.get("/settings/"), "data-push")
