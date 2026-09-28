"""Recurring bills and income: find repeating series, project them forward, remind before bills are due."""
import math
from calendar import monthrange
from collections import defaultdict
from datetime import timedelta
from functools import partial
from statistics import median

from django.db import transaction
from django.utils import timezone

from .models import BillReminder
from .notifications import deliver, recipients
from .reporting import visible_transactions
from .rules import normalize, suggest_keyword

# Allowed gap in days per interval; a gap of about twice the interval (a skipped month) also counts.
INTERVALS = {"weekly": (5, 9), "monthly": (26, 35), "yearly": (350, 380)}
AVERAGE_DAYS = {"weekly": 7, "monthly": 30.44, "yearly": 365.25}
LOOKBACK = timedelta(days=800)  # three yearly payments fit
REMIND_DAYS = 3


def step(day, interval, n):
    """The n-th occurrence after (or, for negative n, before) day. Month ends clamp: the 31st becomes Feb 28."""
    if interval == "weekly":
        return day + timedelta(weeks=n)
    year, month = divmod(day.month - 1 + (n if interval == "monthly" else 12 * n), 12)
    year, month = day.year + year, month + 1
    return day.replace(year=year, month=month, day=min(day.day, monthrange(year, month)[1]))


def occurrences(item, start, end):
    n = math.floor((start - item.anchor_on).days / AVERAGE_DAYS[item.interval]) - 1
    found = []
    while (day := step(item.anchor_on, item.interval, n)) <= end:
        if day >= start:
            found.append(day)
        n += 1
    return found


def key(description):
    name = suggest_keyword(description) or description
    return normalize(name), name


def candidates(user, workspace, today):
    """Series in this workspace's visible, posted spending or income: the same name at least three times, a
    regular weekly/monthly/yearly gap, every amount within 10% of the usual one, and still going."""
    known = set(workspace.recurring.values_list("pattern", flat=True))
    rows = (visible_transactions(user, workspace).filter(pending=False, posted_on__gte=today - LOOKBACK, effective__in=("expense", "income"))
            .values_list("description", "posted_on", "amount_cents", "effective"))
    groups = defaultdict(list)
    for description, day, cents, kind in rows:
        pattern, name = key(description)
        if pattern and pattern not in known:
            groups[pattern, kind].append((day, cents, name))
    found = []
    for (pattern, kind), items in groups.items():
        if len(items) < 3:
            continue
        items.sort()
        days, amounts = [d for d, _, _ in items], [c for _, c, _ in items]
        gaps = [(b - a).days for a, b in zip(days, days[1:])]
        interval = next((name for name, (low, high) in INTERVALS.items() if low <= median(gaps) <= high), None)
        if interval is None:
            continue
        low, high = INTERVALS[interval]
        usual = median(amounts)
        if (all(low <= g <= high or 2 * low <= g <= 2 * high for g in gaps) and all(abs(c - usual) <= usual / 10 for c in amounts)
                and (today - days[-1]).days <= 2 * high):
            found.append({"pattern": pattern, "name": items[-1][2], "kind": "bill" if kind == "expense" else "income", "amount_cents": round(usual),
                          "interval": interval, "anchor_on": step(days[-1], interval, 1), "count": len(items)})
    return sorted(found, key=lambda c: (c["anchor_on"], c["name"]))


def forecast(workspace, today, days=30):
    """Confirmed bills and income over the next days. An estimate only: nothing here counts as spending."""
    end = today + timedelta(days=days)
    items = sorted(((day, item) for item in workspace.recurring.filter(status="confirmed") for day in occurrences(item, today, end)),
                   key=lambda pair: (pair[0], pair[1].name))
    bills = sum(item.amount_cents for _, item in items if item.kind == "bill")
    income = sum(item.amount_cents for _, item in items if item.kind == "income")
    return {"items": items, "bills_cents": bills, "income_cents": income, "left_cents": income - bills, "end": end}


def remind(workspace, today=None):
    """One reminder per person, bill and due date, from three days before. Push and email carry no names or amounts."""
    today = today or timezone.localdate()
    due = [(item, day) for item in workspace.recurring.filter(status="confirmed", kind="bill", remind=True)
           for day in occurrences(item, today, today + timedelta(days=REMIND_DAYS))]
    if not due:
        return
    users = recipients(workspace)
    already = set(BillReminder.objects.filter(recurring__in=[item for item, _ in due], recipient_id__in=users).values_list("recurring_id", "recipient_id", "due_on"))
    new = [BillReminder(recurring=item, recipient_id=user, due_on=day) for item, day in due for user in users if (item.pk, user, day) not in already]
    BillReminder.objects.bulk_create(new, ignore_conflicts=True)
    if fresh := sorted({r.recipient_id for r in new}):
        transaction.on_commit(partial(deliver, fresh, "bill"))
