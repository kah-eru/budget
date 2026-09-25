from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.db.models import Q
from django.utils import timezone

from .invitations import claim_email_send
from .models import Account, Budget, Category, Rule, Transaction, TransactionAnnotation, User, Workspace
from .rules import normalize


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name"]


class TransactionForm(forms.ModelForm):
    amount = forms.DecimalField(label="Amount (USD)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2,
                                help_text="Enter a positive amount; the type decides whether it counts as spending.")

    class Meta:
        model = Transaction
        fields = ["posted_on", "amount", "classification", "pending", "description"]
        labels = {"posted_on": "Date", "classification": "Type", "pending": "Pending (not yet posted)"}
        widgets = {"posted_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["amount"] = Decimal(self.instance.amount_cents) / 100

    def save(self, commit=True):
        self.instance.amount_cents = int(self.cleaned_data["amount"] * 100)
        return super().save(commit)


class AnnotationForm(forms.ModelForm):
    class Meta:
        model = TransactionAnnotation
        fields = ["display_name", "category", "classification", "note"]
        labels = {"classification": "Type"}

    def __init__(self, *args, source, personal, **kwargs):
        super().__init__(*args, **kwargs)
        # This workspace's active categories, plus the current one if it has since been archived.
        workspace = self.instance.workspace
        self.fields["category"].queryset = workspace.categories.filter(Q(archived=False) | Q(pk=self.instance.category_id)).order_by("name")
        self.fields["category"].empty_label = "Uncategorized"
        self.fields["display_name"].help_text = f"Leave blank to show the original: {source.description or '(no description)'}"
        self.fields["classification"].choices = [("", f"Original ({source.get_classification_display()})"), *Transaction.CLASSIFICATIONS]
        self.fields["note"].label = "Personal note (only you)" if personal else "Group note (everyone in this group)"

    def save(self, commit=True):
        if "category" in self.changed_data:
            self.instance.category_source = "manual"
        return super().save(commit)


class TransactionFilterForm(forms.Form):
    q = forms.CharField(label="Search", max_length=100, required=False, widget=forms.TextInput(attrs={"type": "search", "placeholder": "Name or description"}))
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False, empty_label="All accounts")
    person = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="Everyone")
    category = forms.ChoiceField(required=False)
    start = forms.DateField(label="From", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="To", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, accounts, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = [("", "All categories"), ("none", "Uncategorized"),
                                           *((str(c.pk), f"{c.name} (archived)" if c.archived else c.name) for c in workspace.categories.order_by("archived", "name"))]
        self.fields["account"].queryset = accounts.order_by("name", "pk")
        self.fields["person"].queryset = User.objects.filter(pk__in=accounts.values("owner_id")).order_by("username")
        self.fields["person"].label_from_instance = lambda u: u.username

    MAX_DAYS = 731  # two-year interactive range; older history by moving the range

    def clean(self):
        """Missing dates default to one calendar month: this month, To's month, or From's month."""
        data = super().clean()
        start, end = data.get("start"), data.get("end")
        if "start" in self.errors or "end" in self.errors:
            return data
        if not end:
            end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1) if start else timezone.localdate()
        start = start or end.replace(day=1)
        if start > end:
            raise forms.ValidationError("The From date must be on or before the To date.")
        if (end - start).days > self.MAX_DAYS:
            raise forms.ValidationError("Choose a range of two years or less.")
        data.update(start=start, end=end)
        return data

    def apply(self, rows):
        data = self.cleaned_data
        if data["q"]:
            rows = rows.filter(Q(description__icontains=data["q"]) | Q(ann_name__icontains=data["q"]))
        if data["account"]:
            rows = rows.filter(account=data["account"])
        if data["person"]:
            rows = rows.filter(account__owner=data["person"])
        if data["category"]:
            rows = rows.filter(ann__category=None) if data["category"] == "none" else rows.filter(ann__category=int(data["category"]))
        return rows


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "archived"]
        labels = {"archived": "Archived"}
        help_texts = {"archived": "Hidden from new choices. Past transactions keep this category."}

    def clean_name(self):
        name = " ".join(self.cleaned_data["name"].split())
        taken = Category.objects.filter(workspace=self.instance.workspace, name__iexact=name).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("This workspace already has a category with that name.")
        return name


class RuleForm(forms.ModelForm):
    apply_existing = forms.BooleanField(label="Also apply to existing transactions", required=False,
                                        help_text="Categories you picked by hand are kept.")

    class Meta:
        model = Rule
        fields = ["kind", "pattern", "category", "priority", "enabled"]
        labels = {"kind": "Match", "pattern": "Text", "priority": "Priority"}
        help_texts = {"pattern": "Compared with the original bank or entry name, ignoring case and extra spaces.",
                      "priority": "Lower numbers are checked first."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.instance.workspace.categories.filter(
            Q(archived=False) | Q(pk=self.instance.category_id)).order_by("name")

    def clean_pattern(self):
        if not normalize(self.cleaned_data["pattern"]):
            raise forms.ValidationError("Enter the text to match.")
        return " ".join(self.cleaned_data["pattern"].split())


class BudgetForm(forms.ModelForm):
    limit = forms.DecimalField(label="Limit (USD)", min_value=Decimal("0.01"), max_digits=12, decimal_places=2)

    class Meta:
        model = Budget
        fields = ["category", "name_match", "period", "limit"]
        labels = {"name_match": "Or a name containing", "period": "Period"}
        help_texts = {"name_match": "For one merchant across categories, like “STARBUCKS”. Leave blank when you pick a category."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = self.instance.workspace.categories.filter(
            Q(archived=False) | Q(pk=self.instance.category_id)).order_by("name")
        self.fields["category"].empty_label = "No category (use a name)"
        if self.instance.pk:
            self.initial["limit"] = Decimal(self.instance.limit_cents) / 100

    def clean(self):
        data = super().clean()
        data["name_match"] = " ".join(data.get("name_match", "").split())
        if bool(data.get("category")) == bool(data["name_match"]):
            raise forms.ValidationError("Choose a category or enter a name, not both.")
        return data

    def save(self, commit=True):
        self.instance.name_match = self.cleaned_data["name_match"]
        self.instance.limit_cents = int(self.cleaned_data["limit"] * 100)
        return super().save(commit)


class GroupForm(forms.ModelForm):
    class Meta:
        model = Workspace
        fields = ["name"]


class SharingForm(forms.Form):
    accounts = forms.ModelMultipleChoiceField(
        queryset=Account.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple, label="Your accounts to share",
    )
    confirm = forms.BooleanField(label="I understand that everyone in this group can see past and future transactions for the selected accounts.")

    def __init__(self, *args, user, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["accounts"].queryset = Account.objects.filter(owner=user).order_by("name", "pk")
        self.initial["accounts"] = Account.objects.filter(owner=user, shares__workspace=workspace)


class InvitationForm(forms.Form):
    email = forms.EmailField(label="Their email address", max_length=254)
    confirm = forms.BooleanField(label="I understand that this person will see the group's existing shared history and future shared transactions.")

    def __init__(self, *args, personal=False, **kwargs):
        super().__init__(*args, **kwargs)
        if personal:
            self.fields["confirm"].label = "I understand they get their own private login. Nothing of mine is shared with them."


class AcceptInvitationForm(forms.Form):
    confirm = forms.BooleanField(label="I want to join this group. My own accounts will remain private until I choose to share them.")

    def __init__(self, *args, personal=False, **kwargs):
        super().__init__(*args, **kwargs)
        if personal:
            self.fields["confirm"].label = "I want to finish setting up my private Budget login."


class InvitedUserForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username"]


class VerifiedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        for user in super().get_users(email):
            if user.verified_email == user.email.lower() and claim_email_send(user):
                yield user


class CurrentPasswordMixin:
    """A change to login details needs the current password, like Django's own password change."""

    def check_password(self, user):
        if not user.check_password(self.cleaned_data.get("current_password") or ""):
            self.add_error("current_password", "Your current password was entered incorrectly.")


class UsernameChangeForm(CurrentPasswordMixin, forms.ModelForm):
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    class Meta:
        model = User
        fields = ["username"]

    def clean(self):
        data = super().clean()
        self.check_password(self.instance)
        return data


class EmailChangeForm(CurrentPasswordMixin, forms.Form):
    email = forms.EmailField(label="New email address", max_length=254)
    current_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email == self.user.email.lower():
            raise forms.ValidationError("That is already your email address.")
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Another login already uses this email.")
        return email

    def clean(self):
        data = super().clean()
        self.check_password(self.user)
        return data
