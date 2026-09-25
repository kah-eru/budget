from decimal import Decimal

from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.db.models import Q

from .invitations import claim_email_send
from .models import Account, Transaction, TransactionAnnotation, User, Workspace


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
        fields = ["display_name", "classification", "note"]
        labels = {"classification": "Type"}

    def __init__(self, *args, source, personal, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["display_name"].help_text = f"Leave blank to show the original: {source.description or '(no description)'}"
        self.fields["classification"].choices = [("", f"Original ({source.get_classification_display()})"), *Transaction.CLASSIFICATIONS]
        self.fields["note"].label = "Personal note (only you)" if personal else "Group note (everyone in this group)"


class TransactionFilterForm(forms.Form):
    q = forms.CharField(label="Search", max_length=100, required=False, widget=forms.TextInput(attrs={"type": "search", "placeholder": "Name or description"}))
    account = forms.ModelChoiceField(queryset=Account.objects.none(), required=False, empty_label="All accounts")
    person = forms.ModelChoiceField(queryset=User.objects.none(), required=False, empty_label="Everyone")
    start = forms.DateField(label="From", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="To", required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, accounts, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = accounts.order_by("name", "pk")
        self.fields["person"].queryset = User.objects.filter(pk__in=accounts.values("owner_id")).order_by("username")
        self.fields["person"].label_from_instance = lambda u: u.username

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError("The From date must be on or before the To date.")
        return data

    def apply(self, rows):
        data = self.cleaned_data
        if data["q"]:
            rows = rows.filter(Q(description__icontains=data["q"]) | Q(ann_name__icontains=data["q"]))
        if data["account"]:
            rows = rows.filter(account=data["account"])
        if data["person"]:
            rows = rows.filter(account__owner=data["person"])
        if data["start"]:
            rows = rows.filter(posted_on__gte=data["start"])
        if data["end"]:
            rows = rows.filter(posted_on__lte=data["end"])
        return rows


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


class AcceptInvitationForm(forms.Form):
    confirm = forms.BooleanField(label="I want to join this group. My own accounts will remain private until I choose to share them.")


class InvitedUserForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username"]


class VerifiedPasswordResetForm(PasswordResetForm):
    def get_users(self, email):
        for user in super().get_users(email):
            if user.verified_email == user.email.lower() and claim_email_send(user):
                yield user
