"""Goals: progress toward a savings target or a debt payoff, and the monthly amount that reaches it on time."""
import math

from .permissions import visible_accounts


def progress(goal, user, today):
    """A linked account counts only while it is still visible in the goal's workspace; otherwise the typed amount does."""
    account = goal.account if goal.account_id and visible_accounts(user, goal.workspace).filter(pk=goal.account_id).exists() else None
    if account and account.balance_cents is not None:
        done = account.balance_cents if goal.kind == "savings" else (goal.start_cents or 0) - account.balance_cents
    else:
        account, done = None, goal.manual_cents
    done = max(0, done)
    remaining = max(0, goal.target_cents - done)
    monthly = None
    if goal.target_date and remaining:
        months = max(1, (goal.target_date.year - today.year) * 12 + goal.target_date.month - today.month)
        monthly = math.ceil(remaining / months)
    return {"goal": goal, "done_cents": done, "remaining_cents": remaining, "percent": min(100, round(100 * done / goal.target_cents)),
            "monthly_cents": monthly, "linked": account, "overdue": bool(goal.target_date and goal.target_date < today and remaining)}
