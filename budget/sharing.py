from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404
from django.utils import timezone

from .models import Account, AccountShare, Membership, Workspace
from .permissions import get_workspace


def bump_permissions(workspace):
    Workspace.objects.filter(pk=workspace.pk).update(
        permission_revision=F("permission_revision") + 1,
        data_revision=F("data_revision") + 1,
    )


def bump_account_data(account):
    """Invalidate derived output everywhere this account's data is visible."""
    Workspace.objects.filter(
        Q(owner_id=account.owner_id, is_personal=True) | Q(account_shares__account=account)
    ).update(data_revision=F("data_revision") + 1)


@transaction.atomic
def replace_shares(user, workspace_id, account_ids):
    workspace = get_workspace(user, workspace_id, lock=True)
    if workspace.is_personal:
        raise Http404
    owned_ids = set(Account.objects.filter(owner=user, pk__in=account_ids).values_list("pk", flat=True))
    if owned_ids != set(account_ids):
        raise ValidationError("Choose only accounts you own.")
    AccountShare.objects.filter(workspace=workspace, account__owner=user).exclude(account_id__in=owned_ids).delete()
    for account_id in owned_ids:
        AccountShare.objects.get_or_create(workspace=workspace, account_id=account_id)
    bump_permissions(workspace)


@transaction.atomic
def remove_member(user, workspace_id, member_id):
    workspace = get_workspace(user, workspace_id, lock=True)
    if workspace.is_personal or (user.pk != workspace.owner_id and user.pk != member_id):
        raise Http404
    if member_id == workspace.owner_id:
        raise ValidationError("The owner must transfer ownership or delete the group before leaving.")
    membership = Membership.objects.filter(workspace=workspace, user_id=member_id)
    if not membership.exists():
        raise Http404
    AccountShare.objects.filter(workspace=workspace, account__owner_id=member_id).delete()
    member = membership.select_related("user").get().user
    workspace.invitations.filter(email__iexact=member.email, accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
    membership.delete()
    bump_permissions(workspace)
