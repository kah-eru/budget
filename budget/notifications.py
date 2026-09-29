import logging
from functools import partial

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import BudgetAlert, Membership, Workspace
from .account_mail import email_budget_alert
from .push import send_budget_alert
from .reporting import budget_progress

log = logging.getLogger(__name__)


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
    fresh = set()
    # Group spending is the same for every member, so the owner's view computes it once.
    for p in budget_progress(workspace.owner, workspace, budgets, timezone.localdate()):
        if p["over"]:
            already = set(BudgetAlert.objects.filter(budget=p["budget"], period_start=p["start"], recipient_id__in=users).values_list("recipient_id", flat=True))
            BudgetAlert.objects.bulk_create([BudgetAlert(budget=p["budget"], recipient_id=u, period_start=p["start"], silent=silent) for u in users],
                                            ignore_conflicts=True)
            if not silent:
                fresh.update(u for u in users if u not in already)
    # Push and email only real, new crossings, once per person however many budgets crossed. A concurrent
    # evaluation could send twice; pushes share one tag so a device shows one, and the inbox row is unique regardless.
    if fresh:
        transaction.on_commit(partial(deliver, sorted(fresh)))


def deliver(user_ids, what="budget"):
    # Runs after the change committed: a delivery failure is logged, never turned into an error for the saved change.
    for send in (send_budget_alert, email_budget_alert):
        try:
            send(user_ids, what)
        except Exception:
            log.exception("Alert delivery failed")


def baseline_member(workspace, user):
    evaluate(workspace, silent=True, users=[user.pk])


def evaluate_account(account):
    """After an account's data changes: every workspace that can see it."""
    from .recurring import remind  # recurring imports this module
    for workspace in Workspace.objects.filter(Q(owner_id=account.owner_id, is_personal=True) | Q(account_shares__account=account)).distinct():
        evaluate(workspace)
        remind(workspace)
