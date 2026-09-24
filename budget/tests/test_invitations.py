import re
from datetime import timedelta
from unittest.mock import patch

from django.apps import apps
from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone

from budget.models import Account, AccountShare, Membership, User, Workspace


class InvitationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", email="owner@example.com", password="synthetic-password")
        self.friend = User.objects.create_user("friend", email="friend@example.com", password="synthetic-password")
        self.other = User.objects.create_user("other", email="other@example.com", password="synthetic-password")
        self.group = Workspace.objects.create(owner=self.owner, name="Friends")
        self.shared = Account.objects.create(owner=self.owner, name="Shared checking")
        self.private = Account.objects.create(owner=self.owner, name="Private savings")
        AccountShare.objects.create(account=self.shared, workspace=self.group)
        self.invite_url = f"/workspaces/{self.group.pk}/invitations/"
        self.sign_in(self.owner)

    def sign_in(self, user):
        self.client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")

    def email_path(self):
        return re.search(r"http://testserver([^\s]+)", mail.outbox[-1].body).group(1)

    def invite(self, email="friend@example.com"):
        self.sign_in(self.owner)
        response = self.client.post(self.invite_url, {"email": email, "confirm": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(mail.outbox[-1].to, [email.lower()])
        return self.email_path()

    def verify(self, user):
        self.sign_in(user)
        response = self.client.post("/email/verify/")
        self.assertEqual(response.status_code, 302)
        path = self.email_path()
        self.assertEqual(self.client.get(path).status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.verified_email)
        self.assertEqual(self.client.post(path).status_code, 302)
        user.refresh_from_db()
        self.assertEqual(user.verified_email, user.email.lower())
        return path

    def test_invitation_requires_owner_and_history_confirmation(self):
        self.assertContains(self.client.get(self.invite_url), "existing shared history")
        self.assertEqual(self.client.post(self.invite_url, {"email": self.friend.email}).status_code, 400)
        Membership.objects.create(workspace=self.group, user=self.friend)
        for user in (self.friend, self.other):
            self.sign_in(user)
            self.assertEqual(self.client.post(self.invite_url, {"email": "new@example.com", "confirm": "on"}).status_code, 404)

    def test_overlong_email_is_rejected_before_persistence(self):
        from django.core.exceptions import ValidationError
        from budget.invitations import create_invitation

        email = "x" * 64 + "@" + ".".join(["a" * 63, "b" * 63, "c" * 62])
        self.assertEqual(self.client.post(self.invite_url, {"email": email, "confirm": "on"}).status_code, 400)
        with self.assertRaises(ValidationError):
            create_invitation(self.owner, self.group.pk, email)

    def test_owner_can_reach_older_pending_invitations_to_revoke(self):
        Invitation = apps.get_model("budget", "Invitation")
        for index in range(21):
            Invitation.objects.create(workspace=self.group, email=f"pending-{index}@example.com", token_hash=f"{index:064x}", expires_at=timezone.now() + timedelta(days=1))
        self.assertNotContains(self.client.get(self.invite_url), "pending-0@example.com")
        self.assertContains(self.client.get(self.invite_url + "?page=2"), "pending-0@example.com")

    def test_setup_proof_expires_and_is_invalidated_by_revocation(self):
        path = self.invite("new@example.com")
        self.client.logout()
        self.assertEqual(self.client.post(path + "register/").status_code, 302)
        proof_path = self.email_path()
        Invitation = apps.get_model("budget", "Invitation")
        Invitation.objects.update(signup_sent_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(self.client.get(proof_path).status_code, 404)
        Invitation.objects.update(signup_sent_at=timezone.now(), revoked_at=timezone.now())
        self.assertEqual(self.client.get(proof_path).status_code, 404)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_removal_revokes_pending_invites_and_notice_access(self):
        Membership.objects.create(workspace=self.group, user=self.friend)
        path = self.invite()
        self.verify(self.friend)
        self.sign_in(self.owner)
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/members/{self.friend.pk}/remove/").status_code, 302)
        self.sign_in(self.friend)
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 404)
        self.assertEqual(self.client.get(f"/workspaces/{self.group.pk}/").status_code, 404)

    def test_verified_join_is_single_use_and_preserves_private_accounts(self):
        path = self.invite("FRIEND@example.com")
        invitation = apps.get_model("budget", "Invitation").objects.get()
        self.assertNotEqual(invitation.token_hash, path.strip("/").split("/")[-1])
        self.assertEqual(len(invitation.token_hash), 64)
        self.assertAlmostEqual((invitation.expires_at - invitation.created_at).total_seconds(), 604800, delta=2)
        self.sign_in(self.friend)
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 400)
        verification_path = self.verify(self.friend)
        self.assertEqual(self.client.post(verification_path).status_code, 400)
        self.assertEqual(self.client.post(path).status_code, 400)
        self.assertFalse(Membership.objects.filter(workspace=self.group, user=self.friend).exists())
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 302)
        page = self.client.get(f"/workspaces/{self.group.pk}/")
        self.assertContains(page, "Shared checking")
        self.assertNotContains(page, "Private savings")
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 404)
        self.group.refresh_from_db()
        self.assertEqual(self.group.permission_revision, 1)
        self.assertEqual(self.group.data_revision, 1)
        self.sign_in(self.owner)
        self.assertContains(self.client.get(f"/workspaces/{self.group.pk}/"), "friend joined")

    def test_wrong_email_expired_and_revoked_invites_cannot_join(self):
        path = self.invite()
        self.verify(self.other)
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 400)
        self.assertNotContains(self.client.get(path), "Shared checking")
        self.verify(self.friend)
        Invitation = apps.get_model("budget", "Invitation")
        Invitation.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 404)
        Invitation.objects.update(expires_at=timezone.now() + timedelta(days=1))
        invitation = Invitation.objects.get()
        self.sign_in(self.owner)
        revoke = f"{self.invite_url}{invitation.pk}/revoke/"
        self.assertEqual(self.client.get(revoke).status_code, 405)
        self.assertEqual(self.client.post(revoke).status_code, 302)
        self.sign_in(self.friend)
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 404)
        self.assertFalse(Membership.objects.filter(workspace=self.group, user=self.friend).exists())

    def test_invited_signup_cannot_reserve_email_without_mailbox_proof(self):
        path = self.invite("new@example.com")
        self.client.logout()
        signup = path + "register/"
        response = self.client.post(signup, {"username": "newfriend", "email": "other@example.com", "password1": "A-long-synthetic-passphrase-83", "password2": "A-long-synthetic-passphrase-83"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())
        proof_path = self.email_path()
        self.assertNotEqual(proof_path, signup)
        self.assertEqual(mail.outbox[-1].to, ["new@example.com"])
        self.assertEqual(self.client.post(proof_path, {"username": "newfriend", "password1": "A-long-synthetic-passphrase-83", "password2": "A-long-synthetic-passphrase-83"}).status_code, 302)
        user = User.objects.get(username="newfriend")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.verified_email, user.email)
        self.assertFalse(Membership.objects.filter(user=user).exists())
        self.assertEqual(self.client.post(proof_path, {"username": "impostor", "password1": "A-long-synthetic-passphrase-83", "password2": "A-long-synthetic-passphrase-83"}).status_code, 404)
        self.sign_in(user)
        self.assertEqual(self.client.post(path, {"confirm": "on"}).status_code, 302)
        self.assertFalse(AccountShare.objects.filter(account__owner=user).exists())
        self.client.logout()
        self.assertEqual(self.client.get("/signup/").status_code, 404)
        self.assertEqual(self.client.get("/invitations/invalid/register/").status_code, 404)

    def test_existing_account_cannot_be_replaced_through_registration(self):
        path = self.invite()
        self.client.logout()
        response = self.client.post(path + "register/", {"username": "impostor", "password1": "A-long-synthetic-passphrase-83", "password2": "A-long-synthetic-passphrase-83"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="impostor").exists())
        self.friend.refresh_from_db()
        self.assertTrue(self.friend.check_password("synthetic-password"))

    def test_verification_is_bound_to_user_email_and_expires(self):
        self.sign_in(self.friend)
        self.assertEqual(self.client.post("/email/verify/").status_code, 302)
        path = self.email_path()
        self.sign_in(self.other)
        self.assertEqual(self.client.post(path).status_code, 400)
        self.sign_in(self.friend)
        User.objects.filter(pk=self.friend.pk).update(email="changed@example.com")
        self.assertEqual(self.client.post(path).status_code, 400)
        User.objects.filter(pk=self.friend.pk).update(email="friend@example.com")
        with self.settings(PASSWORD_RESET_TIMEOUT=-1):
            self.assertEqual(self.client.post(path).status_code, 400)

    def test_invitation_and_verification_mail_are_throttled_and_failures_are_visible(self):
        path = self.invite()
        self.assertEqual(self.client.post(self.invite_url, {"email": self.friend.email, "confirm": "on"}).status_code, 400)
        self.assertEqual(len(mail.outbox), 1)
        self.sign_in(self.friend)
        self.assertEqual(self.client.post("/email/verify/").status_code, 302)
        self.assertEqual(self.client.post("/email/verify/").status_code, 400)
        self.assertEqual(len(mail.outbox), 2)
        self.sign_in(self.owner)
        with patch("django.core.mail.backends.locmem.EmailBackend.send_messages", side_effect=OSError("offline")):
            response = self.client.post(self.invite_url, {"email": "new@example.com", "confirm": "on"})
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "could not be sent", status_code=400)
        self.assertFalse(apps.get_model("budget", "Invitation").objects.filter(email="new@example.com", revoked_at__isnull=True).exists())

    def test_csrf_required_and_token_pages_are_private(self):
        path = self.invite()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.friend, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(csrf_client.post(path, {"confirm": "on"}).status_code, 403)
        self.assertEqual(csrf_client.post("/email/verify/").status_code, 403)
        page = self.client.get(path)
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["X-Robots-Tag"], "noindex, nofollow")


class RecoveryTests(TestCase):
    def test_only_verified_email_can_reset_password_without_disclosing_registration(self):
        user = User.objects.create_user("recover", email="recover@example.com", password="old-synthetic-password")
        response = self.client.post("/password-reset/", {"email": user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)
        User.objects.filter(pk=user.pk).update(verified_email=user.email)
        response = self.client.post("/password-reset/", {"email": user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        for email in (user.email, "unknown@example.com"):
            self.assertEqual(self.client.post("/password-reset/", {"email": email}).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r"http://testserver([^\s]+)", mail.outbox[0].body).group(1)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(response["Location"], {"new_password1": "New-synthetic-passphrase-42", "new_password2": "New-synthetic-passphrase-42"})
        self.assertRedirects(response, "/password-reset/complete/")
        user.refresh_from_db()
        self.assertTrue(user.check_password("New-synthetic-passphrase-42"))
        self.assertContains(self.client.get(path), "invalid")
