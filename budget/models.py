from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class User(AbstractUser):
    verified_email = models.EmailField(blank=True, editable=False)
    email_last_sent_at = models.DateTimeField(null=True, editable=False)

    class Meta(AbstractUser.Meta):
        constraints = [models.UniqueConstraint(Lower("email"), condition=~Q(email=""), name="unique_nonempty_email")]


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


class Invitation(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    signup_token_hash = models.CharField(max_length=64, blank=True)
    signup_sent_at = models.DateTimeField(null=True)


class MembershipNotice(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    member_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)


class Transaction(models.Model):
    # Positive cents; classification decides whether it adds to or reduces spending.
    CLASSIFICATIONS = [("expense", "Expense"), ("refund", "Refund"), ("income", "Income"), ("transfer", "Transfer or card payment")]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    posted_on = models.DateField()
    amount_cents = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="USD", editable=False)
    classification = models.CharField(max_length=10, choices=CLASSIFICATIONS, default="expense")
    pending = models.BooleanField(default=False)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        indexes = [models.Index(fields=["account", "posted_on", "id"])]
        constraints = [
            models.CheckConstraint(condition=Q(amount_cents__gt=0), name="transaction_amount_positive"),
            models.CheckConstraint(condition=Q(currency="USD"), name="transaction_usd_only"),
        ]


class TransactionAnnotation(models.Model):
    # Per-workspace overlay; the source Transaction is never modified. Null classification = use source.
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="annotations")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="annotations")
    display_name = models.CharField(max_length=200, blank=True)
    classification = models.CharField(max_length=10, choices=Transaction.CLASSIFICATIONS, null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["transaction", "workspace"], name="annotation_one_per_workspace")]
