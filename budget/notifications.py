from django.db.models import Q
from django.utils import timezone

from .models import BudgetAlert, Membership, Workspace
from .reporting import budget_progress


def recipients(workspace):
    if workspace.is_personal:
        return [workspace.owner_id]
    return [workspace.owner_id, *Membership.objects.filter(workspace=workspace).values_list("user_id", flat=True)]


def evaluate(workspace, *, silent=False, budgets=None, users=None):
    """Record an alert for every budget whose current period is over its limit (posted spending only).
    Closed periods are never evaluated, so backdated edits update reports without old alerts."""
    budgets = list(workspace.budgets.select_related("category")) if budgets is None else budgets
    if not budgets:
        return
    users = recipients(workspace) if users is None else users
    # Group spending is the same for every member, so the owner's view computes it once.
    for p in budget_progress(workspace.owner, workspace, budgets, timezone.localdate()):
        if p["over"]:
            BudgetAlert.objects.bulk_create([BudgetAlert(budget=p["budget"], recipient_id=u, period_start=p["start"], silent=silent) for u in users],
                                            ignore_conflicts=True)


def baseline_member(workspace, user):
    evaluate(workspace, silent=True, users=[user.pk])


def evaluate_account(account):
    """After an account's data changes: every workspace that can see it."""
    for workspace in Workspace.objects.filter(Q(owner_id=account.owner_id, is_personal=True) | Q(account_shares__account=account)).distinct():
        evaluate(workspace)
