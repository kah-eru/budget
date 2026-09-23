from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class User(AbstractUser):
    pass


class Workspace(models.Model):
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_workspaces")
    is_personal = models.BooleanField(default=False)
    data_revision = models.PositiveBigIntegerField(default=0)
    permission_revision = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner"], condition=Q(is_personal=True), name="one_personal_workspace")]


class Membership(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_membership")]


class Account(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class AccountShare(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="shares")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="account_shares")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "workspace"], name="unique_account_share")]
