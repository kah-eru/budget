"""PostgreSQL row-locking checks: each thread uses its own database session, like a second web process."""
import threading
import time
import unittest

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.http import Http404
from django.test import TransactionTestCase

from budget.invitations import accept_invitation, create_invitation
from budget.models import Account, AccountShare, Invitation, Membership, Workspace
from budget.sharing import replace_shares

HOLD = 1.5  # seconds the first session keeps the workspace row locked


def in_session(fn):
    """Run fn in a new thread (new DB session); return a handle whose .join() yields (result, error, seconds)."""
    out = {}

    def run():
        start = time.monotonic()
        try:
            out["result"] = fn()
        except Exception as exc:  # noqa: BLE001 - the error is the outcome under test
            out["error"] = exc
        finally:
            out["seconds"] = time.monotonic() - start
            connection.close()

    thread = threading.Thread(target=run)
    thread.start()

    def join():
        thread.join(30)
        return out.get("result"), out.get("error"), out["seconds"]

    return join


@unittest.skipUnless(connection.vendor == "postgresql", "row locking needs PostgreSQL")
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        users = get_user_model().objects
        self.alice = users.create_user("alice", password="synthetic-password", email="alice@example.test")
        self.bob = users.create_user("bob", password="synthetic-password", email="bob@example.test", verified_email="bob@example.test")
        self.group = Workspace.objects.create(owner=self.alice, name="Partner group")

    def test_share_waits_for_removal_then_is_denied(self):
        Membership.objects.create(workspace=self.group, user=self.bob)
        account = Account.objects.create(owner=self.bob, name="Bob card")
        locked, release = threading.Event(), threading.Event()

        def removal():  # owner removes bob, holding the workspace lock until released
            with transaction.atomic():
                Workspace.objects.select_for_update().get(pk=self.group.pk)
                Membership.objects.filter(workspace=self.group, user=self.bob).delete()
                locked.set()
                release.wait(10)

        remover = in_session(removal)
        self.assertTrue(locked.wait(10))
        sharer = in_session(lambda: replace_shares(self.bob, self.group.pk, [account.pk]))
        time.sleep(HOLD)
        release.set()
        remover()
        _, error, seconds = sharer()
        self.assertIsInstance(error, Http404)
        self.assertGreaterEqual(seconds, HOLD * 0.9, "share did not wait for the lock")
        self.assertFalse(AccountShare.objects.filter(workspace=self.group).exists())

    def test_parallel_invites_to_same_address_create_one(self):
        gate = threading.Barrier(2)

        def invite():
            gate.wait(10)
            return create_invitation(self.alice, self.group.pk, "carol@example.test")

        outcomes = [join() for join in [in_session(invite), in_session(invite)]]
        self.assertEqual(Invitation.objects.filter(email="carol@example.test").count(), 1)
        self.assertEqual(sum(isinstance(e, ValidationError) for _, e, _ in outcomes), 1, outcomes)

    def test_parallel_accepts_join_once(self):
        _, token = create_invitation(self.alice, self.group.pk, "bob@example.test")
        gate = threading.Barrier(2)

        def accept():
            gate.wait(10)
            return accept_invitation(self.bob, token)

        outcomes = [join() for join in [in_session(accept), in_session(accept)]]
        self.assertEqual(Membership.objects.filter(workspace=self.group, user=self.bob).count(), 1)
        self.assertEqual(sum(e is None for _, e, _ in outcomes), 1, outcomes)
        self.assertEqual(sum(isinstance(e, Http404) for _, e, _ in outcomes), 1, outcomes)
        self.group.refresh_from_db()
        self.assertEqual(self.group.permission_revision, 1)

    def test_session_written_by_one_process_is_read_by_another(self):
        store = SessionStore()
        store["_auth_user_id"] = str(self.bob.pk)
        store.create()
        result, error, _ = in_session(lambda: SessionStore(store.session_key).load())()
        self.assertIsNone(error)
        self.assertEqual(result.get("_auth_user_id"), str(self.bob.pk))
