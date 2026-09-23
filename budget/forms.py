from django import forms

from .models import Account, Workspace


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ["name"]


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
