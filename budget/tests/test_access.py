from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from budget.models import Account, AccountShare, Membership, Workspace


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice, cls.bob, cls.eve = [
            get_user_model().objects.create_user(name, password="synthetic-password")
            for name in ("alice", "bob", "eve")
        ]
        cls.personal, _ = Workspace.objects.get_or_create(owner=cls.alice, is_personal=True, defaults={"name": "Personal"})
        cls.group = Workspace.objects.create(owner=cls.alice, name="Partner group")
        Membership.objects.create(workspace=cls.group, user=cls.bob)
        cls.other = Workspace.objects.create(owner=cls.eve, name="Unrelated group")
        cls.private = Account.objects.create(owner=cls.alice, name="Private savings")
        cls.shared = Account.objects.create(owner=cls.alice, name="Shared checking")
        cls.bobs = Account.objects.create(owner=cls.bob, name="Bob checking")
        AccountShare.objects.create(account=cls.shared, workspace=cls.group)
        AccountShare.objects.create(account=cls.bobs, workspace=cls.group)

    def setUp(self):
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")

    def account_url(self, account, workspace=None):
        return f"/workspaces/{(workspace or self.group).pk}/accounts/{account.pk}/"

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_new_users_get_exactly_one_personal_workspace(self):
        self.assertEqual(Workspace.objects.filter(owner=self.bob, is_personal=True).count(), 1)

    def test_group_lists_only_shared_accounts(self):
        response = self.client.get(f"/workspaces/{self.group.pk}/")
        self.assertContains(response, "Shared checking")
        self.assertContains(response, "Bob checking")
        self.assertNotContains(response, "Private savings")

    def test_direct_access_cannot_reveal_private_or_other_groups(self):
        self.assertEqual(self.client.get(self.account_url(self.private)).status_code, 404)
        self.assertEqual(self.client.get(self.account_url(self.shared, self.other)).status_code, 404)
        self.assertEqual(self.client.get(self.account_url(self.private, self.personal)).status_code, 404)

    def test_personal_shows_only_own_accounts(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        response = self.client.get(f"/workspaces/{self.personal.pk}/")
        self.assertContains(response, "Private savings")
        self.assertNotContains(response, "Bob checking")

    def test_revoked_share_disappears_from_list_and_detail(self):
        AccountShare.objects.filter(account=self.shared, workspace=self.group).delete()
        self.assertNotContains(self.client.get(f"/workspaces/{self.group.pk}/"), "Shared checking")
        self.assertEqual(self.client.get(self.account_url(self.shared)).status_code, 404)

    def test_removed_member_loses_workspace_and_their_shares_are_not_visible(self):
        Membership.objects.filter(workspace=self.group, user=self.bob).delete()
        self.assertEqual(self.client.get(self.account_url(self.shared)).status_code, 404)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.assertNotContains(self.client.get(f"/workspaces/{self.group.pk}/"), "Bob checking")

    def test_only_account_owner_can_change_sharing(self):
        response = self.client.post(f"/workspaces/{self.group.pk}/sharing/", {"accounts": [self.private.pk], "confirm": "on"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AccountShare.objects.filter(account=self.private).exists())
        self.assertTrue(AccountShare.objects.filter(account=self.bobs, workspace=self.group).exists())

    def test_sharing_requires_explicit_history_confirmation(self):
        response = self.client.post(f"/workspaces/{self.group.pk}/sharing/", {"accounts": [self.bobs.pk]})
        self.assertEqual(response.status_code, 400)

    def test_sharing_replaces_only_actors_grants_and_bumps_revisions(self):
        response = self.client.post(f"/workspaces/{self.group.pk}/sharing/", {"confirm": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccountShare.objects.filter(account=self.bobs, workspace=self.group).exists())
        self.assertTrue(AccountShare.objects.filter(account=self.shared, workspace=self.group).exists())
        self.group.refresh_from_db()
        self.assertEqual(self.group.permission_revision, 1)
        self.assertEqual(self.group.data_revision, 1)

    def test_share_to_unrelated_or_personal_workspace_is_rejected(self):
        for workspace in [self.other, self.personal]:
            self.assertEqual(self.client.post(f"/workspaces/{workspace.pk}/sharing/", {"confirm": "on"}).status_code, 404)

    def test_removal_revokes_membership_and_grants(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        response = self.client.post(f"/workspaces/{self.group.pk}/members/{self.bob.pk}/remove/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Membership.objects.filter(workspace=self.group, user=self.bob).exists())
        self.assertFalse(AccountShare.objects.filter(account=self.bobs, workspace=self.group).exists())

    def test_member_cannot_remove_owner_or_other_members(self):
        response = self.client.post(f"/workspaces/{self.group.pk}/members/{self.alice.pk}/remove/")
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_leave_without_transfer(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/members/{self.alice.pk}/remove/").status_code, 400)

    def test_mutations_require_post_and_csrf(self):
        url = f"/workspaces/{self.group.pk}/members/{self.bob.pk}/remove/"
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertEqual(csrf_client.post(url).status_code, 403)

    def test_private_responses_are_not_indexable_or_cacheable(self):
        response = self.client.get(f"/workspaces/{self.group.pk}/")
        self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertIn("no-store", response.headers.get("Cache-Control", ""))

    def test_create_account_cannot_assign_someone_else_as_owner(self):
        response = self.client.post("/accounts/new/", {"name": "Manual account", "owner": self.alice.pk})
        self.assertEqual(response.status_code, 302)
        account = Account.objects.get(name="Manual account")
        self.assertEqual(account.owner, self.bob)
        self.assertFalse(account.shares.exists())

    def test_create_group_keeps_private_accounts_private(self):
        response = self.client.post("/groups/new/", {"name": "Friends"})
        self.assertEqual(response.status_code, 302)
        group = Workspace.objects.get(name="Friends")
        self.assertEqual(group.owner, self.bob)
        self.assertFalse(group.is_personal)
        self.assertFalse(group.account_shares.exists())

    def test_owner_shares_different_accounts_to_different_groups(self):
        friends = Workspace.objects.create(owner=self.alice, name="Friends")
        Membership.objects.create(workspace=friends, user=self.bob)
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        response = self.client.post(f"/workspaces/{friends.pk}/sharing/", {"accounts": [self.private.pk], "confirm": "on"})
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.bob, backend="django.contrib.auth.backends.ModelBackend")
        self.assertContains(self.client.get(f"/workspaces/{friends.pk}/"), "Private savings")
        self.assertNotContains(self.client.get(f"/workspaces/{friends.pk}/"), "Shared checking")
        self.assertNotContains(self.client.get(f"/workspaces/{self.group.pk}/"), "Private savings")

    def test_accidental_personal_membership_does_not_grant_access(self):
        Membership.objects.create(workspace=self.personal, user=self.bob)
        self.assertEqual(self.client.get(f"/workspaces/{self.personal.pk}/").status_code, 404)

    def test_only_owner_can_edit_visible_accounts(self):
        from budget.permissions import editable_accounts

        self.assertEqual(list(editable_accounts(self.bob, self.group)), [self.bobs])

    def test_sharing_labels_identify_owned_accounts_without_leaking_private_names(self):
        response = self.client.get(f"/workspaces/{self.group.pk}/sharing/")
        self.assertContains(response, "Bob checking")
        self.assertNotContains(response, "Private savings")
        self.assertNotContains(response, "Account object")

    def test_member_can_leave_and_cannot_reshare_afterward(self):
        response = self.client.post(f"/workspaces/{self.group.pk}/members/{self.bob.pk}/remove/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccountShare.objects.filter(account=self.bobs, workspace=self.group).exists())
        self.assertEqual(self.client.post(f"/workspaces/{self.group.pk}/sharing/", {"accounts": [self.bobs.pk], "confirm": "on"}).status_code, 404)
