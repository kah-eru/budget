from decimal import Decimal

from django import forms
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm

from .invitations import claim_email_send
from .models import Account, Transaction, User, Workspace


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
