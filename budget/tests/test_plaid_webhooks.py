import hashlib
import json
import time
from unittest import mock

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from budget import plaid as bank
from budget.models import Account, BankConnection, Transaction
from budget.tests.test_plaid import KEYS, page, txn

SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())


def signed(payload, *, iat=None, key=SIGNING_KEY, alg="ES256", body=None):
    body = json.dumps(payload).encode() if body is None else body
    claims = {"iat": int(time.time()) if iat is None else iat, "request_body_sha256": hashlib.sha256(json.dumps(payload).encode()).hexdigest()}
    return body, jwt.encode(claims, key, algorithm=alg, headers={"kid": "synthetic-key-1"})


@override_settings(**KEYS)
@mock.patch("budget.plaid._webhook_key", return_value=SIGNING_KEY.public_key())
class WebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = get_user_model().objects.create_user("alice", password="synthetic-password")

    def setUp(self):
        self.connection = BankConnection.objects.create(owner=self.alice, item_id="item-1", access_token=bank.encrypt("access-sandbox-1"),
                                                        institution_name="First Platypus Bank", institution_id="ins_109508")
        self.checking = Account.objects.create(owner=self.alice, name="Plaid Checking", connection=self.connection, provider_account_id="acc-1", mask="0000")
        self.plaid = Client(enforce_csrf_checks=True)  # Plaid posts without a CSRF token or session

    def post(self, body, token):
        headers = {"HTTP_PLAID_VERIFICATION": token} if token else {}
        return self.plaid.post("/plaid/webhook/", body, content_type="application/json", **headers)

    def updates(self, item_id="item-1"):
        return {"webhook_type": "TRANSACTIONS", "webhook_code": "SYNC_UPDATES_AVAILABLE", "item_id": item_id}

    def test_a_signed_update_syncs(self, _):
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]):
            self.assertEqual(self.post(*signed(self.updates())).status_code, 200)
        self.assertTrue(Transaction.objects.filter(provider_id="t1").exists())

    def test_forged_stale_or_tampered_webhooks_are_refused(self, _):
        other = ec.generate_private_key(ec.SECP256R1())
        attempts = [
            signed(self.updates(), body=json.dumps({**self.updates(), "item_id": "item-2"}).encode()),  # body changed after signing
            signed(self.updates(), iat=int(time.time()) - 600),  # older than five minutes
            signed(self.updates(), key=other),  # not Plaid's key
            signed(self.updates(), key="shared-secret-guess", alg="HS256"),
            (json.dumps(self.updates()).encode(), ""),
            (json.dumps(self.updates()).encode(), "not-a-jwt"),
        ]
        with mock.patch("budget.plaid._page") as fetched:
            for body, token in attempts:
                self.assertEqual(self.post(body, token).status_code, 400)
        fetched.assert_not_called()

    def test_unknown_items_are_acknowledged_and_ignored(self, _):
        with mock.patch("budget.plaid._page") as fetched:
            self.assertEqual(self.post(*signed(self.updates("item-unknown"))).status_code, 200)
        fetched.assert_not_called()

    def test_login_required_then_repaired(self, _):
        error = {"webhook_type": "ITEM", "webhook_code": "ERROR", "item_id": "item-1", "error": {"error_code": "ITEM_LOGIN_REQUIRED"}}
        self.post(*signed(error))
        connection = BankConnection.objects.get(pk=self.connection.pk)
        self.assertTrue(connection.needs_reconnect)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.assertContains(self.client.get("/settings/"), f"/banks/{connection.pk}/reconnect/")
        self.post(*signed({"webhook_type": "ITEM", "webhook_code": "LOGIN_REPAIRED", "item_id": "item-1"}))
        self.assertFalse(BankConnection.objects.get(pk=self.connection.pk).needs_reconnect)

    def test_an_update_during_a_running_sync_is_not_lost(self, _):
        def first_page(token, cursor):
            # A webhook lands while this sync is fetching: it can't start a second sync, so it leaves a flag.
            self.assertEqual(self.post(*signed(self.updates())).status_code, 200)
            return page(added=[txn("t1", "4.50")], cursor="c1")
        pages = iter([first_page, lambda token, cursor: page(added=[txn("t2", "6.00")], cursor="c2")])
        with mock.patch("budget.plaid._page", side_effect=lambda token, cursor: next(pages)(token, cursor)) as fetched:
            self.assertEqual(bank.sync(self.connection), ("ok", 2))
        self.assertEqual(fetched.call_count, 2)
        self.assertEqual(BankConnection.objects.get(pk=self.connection.pk).cursor, "c2")

    def test_a_crashed_sync_frees_its_claim(self, _):
        BankConnection.objects.filter(pk=self.connection.pk).update(sync_started_at=timezone.now() - bank.LEASE * 2)
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]):
            self.assertEqual(bank.sync(self.connection)[0], "ok")


@override_settings(**KEYS, SITE_URL="https://budget.example")
class ReconnectAndDuplicateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob = [get_user_model().objects.create_user(n, password="synthetic-password") for n in ("alice", "bob")]

    def setUp(self):
        self.connection = BankConnection.objects.create(owner=self.alice, item_id="item-1", access_token=bank.encrypt("access-sandbox-1"),
                                                        institution_name="First Platypus Bank", institution_id="ins_109508",
                                                        status="error", error_code="ITEM_LOGIN_REQUIRED")
        Account.objects.create(owner=self.alice, name="Plaid Checking ••0000", connection=self.connection, provider_account_id="acc-1", mask="0000")
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")

    def test_link_tokens_register_the_webhook_and_update_mode_uses_the_item(self):
        with mock.patch("budget.plaid._call") as call:
            call.return_value.link_token = "link-sandbox-synthetic"
            bank.link_token(self.alice)
            self.assertEqual(call.call_args.args[1].webhook, "https://budget.example/plaid/webhook/")
            bank.link_token(self.alice, self.connection)
            request = call.call_args.args[1]
            self.assertEqual(request.access_token, "access-sandbox-1")
            self.assertNotIn("products", request.to_dict())

    @mock.patch("budget.plaid.link_token", return_value="link-sandbox-synthetic")
    def test_reconnect_clears_the_error_and_syncs(self, _):
        response = self.client.get(f"/banks/{self.connection.pk}/reconnect/")
        self.assertContains(response, "Reconnect First Platypus Bank")
        self.assertContains(response, f'data-exchange="/banks/{self.connection.pk}/reconnected/"')
        with mock.patch("budget.plaid._page", side_effect=[page(added=[txn("t1", "4.50")])]):
            response = self.client.post(f"/banks/{self.connection.pk}/reconnected/", json.dumps({"public_token": "public-sandbox-3"}),
                                        content_type="application/json")
        self.assertEqual(response.json()["next"], "/settings/")
        connection = BankConnection.objects.get(pk=self.connection.pk)
        self.assertEqual((connection.status, connection.error_code), ("ok", ""))
        self.assertTrue(Transaction.objects.exists())
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.get(f"/banks/{self.connection.pk}/reconnect/").status_code, 404)

    @mock.patch("budget.plaid.accounts", return_value={"institution_id": "ins_109508", "accounts": [
        {"id": "acc-9", "name": "Plaid Checking", "mask": "0000", "type": "depository", "subtype": "checking"},
        {"id": "acc-8", "name": "Plaid Saving", "mask": "1111", "type": "depository", "subtype": "savings"}]})
    def test_a_second_connection_to_the_same_bank_is_flagged(self, _):
        second = BankConnection.objects.create(owner=self.alice, item_id="item-2", access_token=bank.encrypt("access-sandbox-2"), institution_name="First Platypus Bank")
        response = self.client.get(f"/banks/{second.pk}/accounts/")
        self.assertContains(response, "already connected First Platypus Bank")
        self.assertContains(response, "Looks like one you already import")
        self.assertContains(response, 'value="acc-9">')  # unticked: no "checked" right after the value
        self.assertContains(response, 'value="acc-8" checked>')
        self.assertEqual(BankConnection.objects.get(pk=second.pk).institution_id, "ins_109508")
