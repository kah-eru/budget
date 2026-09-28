from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import Account, Membership, Workspace


def visible_workspaces(user):
    if not user.is_authenticated:
        return Workspace.objects.none()
    memberships = Membership.objects.filter(user=user).values("workspace_id")
    return Workspace.objects.filter(Q(owner=user) | Q(is_personal=False, pk__in=memberships))


def get_workspace(user, workspace_id, *, lock=False):
    # Lock before rechecking membership so mutations serialize with removal.
    if lock:
        get_object_or_404(Workspace.objects.select_for_update(), pk=workspace_id)
    return get_object_or_404(visible_workspaces(user), pk=workspace_id)


def visible_accounts(user, workspace):
    workspace = get_workspace(user, workspace.pk)
    if workspace.is_personal:
        return Account.objects.filter(owner=user)
    members = Membership.objects.filter(workspace=workspace).values("user_id")
    return Account.objects.filter(shares__workspace=workspace).filter(
        Q(owner=workspace.owner) | Q(owner_id__in=members)
    )


def editable_accounts(user, workspace):
    return visible_accounts(user, workspace).filter(owner=user)
