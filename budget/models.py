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
    # Null = estimate from the last three complete months of posted income (reporting.disposable).
    expected_income_cents = models.BigIntegerField(null=True, blank=True)

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


STANDARD_CATEGORIES = ["Groceries", "Dining", "Housing", "Utilities", "Transport", "Shopping", "Health", "Entertainment", "Subscriptions", "Travel"]


class Category(models.Model):
    # Archived categories stay on past transactions but leave every picker; never deleted while referenced.
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=60)
    archived = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(Lower("name"), "workspace", name="category_name_unique_per_workspace")]

    def __str__(self):
        return self.name


class TransactionAnnotation(models.Model):
    # Per-workspace overlay; the source Transaction is never modified. Null classification = use source.
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="annotations")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="annotations")
    display_name = models.CharField(max_length=200, blank=True)
    classification = models.CharField(max_length=10, choices=Transaction.CLASSIFICATIONS, null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    category = models.ForeignKey(Category, on_delete=models.RESTRICT, null=True, blank=True)
    # "manual" choices (including a manual Uncategorized) are never changed by rules.
    category_source = models.CharField(max_length=6, choices=[("manual", "Manual"), ("rule", "Rule")], blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["transaction", "workspace"], name="annotation_one_per_workspace")]


class Rule(models.Model):
    # Matches the original description, never the edited display name. Lower priority runs first; ties by id.
    KINDS = [("contains", "Name contains"), ("exact", "Name is exactly")]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="rules")
    kind = models.CharField(max_length=8, choices=KINDS, default="contains")
    pattern = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="rules")
    priority = models.PositiveIntegerField(default=100)
    enabled = models.BooleanField(default=True)
    # Optional two-way split template: split_percent of the amount to split_category, the rest to category.
    # ponytail: two lines only; add a template-lines table if someone needs three-way rule splits.
    split_category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name="split_rules")
    split_percent = models.PositiveSmallIntegerField(null=True, blank=True)

    @property
    def first_percent(self):
        return 100 - self.split_percent


class Budget(models.Model):
    # Targets one category or one name match (contains, same normalization as rules). No rollover between periods.
    PERIODS = [("month", "Monthly"), ("year", "Yearly")]
    # fixed: a monthly bill (limit = expected amount); irregular: a yearly total set aside monthly; flexible: a limit.
    KINDS = [("flexible", "Flexible spending"), ("fixed", "Fixed bill"), ("irregular", "Yearly or irregular cost")]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="budgets")
    kind = models.CharField(max_length=9, choices=KINDS, default="flexible")
    due_day = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name="budgets")
    name_match = models.CharField(max_length=100, blank=True)
    period = models.CharField(max_length=5, choices=PERIODS, default="month")
    limit_cents = models.BigIntegerField()

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(limit_cents__gt=0), name="budget_limit_positive"),
            models.CheckConstraint(condition=Q(category__isnull=False, name_match="") | Q(category__isnull=True) & ~Q(name_match=""), name="budget_one_target"),
        ]

    def __str__(self):
        return self.category.name if self.category_id else f"Name contains “{self.name_match}”"


class BudgetAlert(models.Model):
    # One row per budget, recipient and period, ever: the database makes a second crossing a no-op.
    # silent rows are baselines (already over when the budget was set or the member joined) and never show.
    # No amounts are stored; the inbox recomputes them from what the recipient can see now.
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name="alerts")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="budget_alerts")
    period_start = models.DateField()
    silent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["budget", "recipient", "period_start"], name="budget_alert_once_per_period")]


class SplitLine(models.Model):
    # A per-workspace split: lines sum exactly to the transaction amount (checked in SplitForm) and replace the
    # overlay category in that workspace's reports and budgets. The line takes the parent's classification and status.
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name="split_lines")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="split_lines")
    category = models.ForeignKey(Category, on_delete=models.RESTRICT, related_name="split_lines")
    amount_cents = models.BigIntegerField()
    from_rule = models.BooleanField(default=False)  # written by a rule's split template; hand-made splits are never touched by rules

    class Meta:
        indexes = [models.Index(fields=["workspace", "transaction"])]
        constraints = [models.CheckConstraint(condition=Q(amount_cents__gt=0), name="split_line_amount_positive")]


class PushSubscription(models.Model):
    # One browser/device's Web Push subscription. The endpoint is validated against known push services (push.py).
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
