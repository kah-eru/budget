from datetime import date, timedelta

from django.db.models import F, FilteredRelation, Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth

from .models import SplitLine, Transaction
from .permissions import visible_accounts
from .rules import normalize


def annotated(transactions, workspace):
    """Attach this workspace's overlay only: ann_name, ann_note, ann_category and effective classification."""
    return transactions.annotate(
        ann=FilteredRelation("annotations", condition=Q(annotations__workspace=workspace)),
        ann_name=F("ann__display_name"), ann_note=F("ann__note"), ann_category=F("ann__category__name"),
        effective=Coalesce("ann__classification", "classification"),
    )


def visible_transactions(user, workspace):
    """Every transaction this user may see in this workspace, with the workspace overlay attached."""
    return annotated(Transaction.objects.filter(account__in=visible_accounts(user, workspace)), workspace)


def _sums():
    def total(q):
        return Coalesce(Sum("amount_cents", filter=q), 0)

    expense, refund, income = Q(effective="expense"), Q(effective="refund"), Q(effective="income")
    posted, pending = Q(pending=False), Q(pending=True)
    return {"pe": total(posted & expense), "pr": total(posted & refund), "qe": total(pending & expense), "qr": total(pending & refund), "inc": total(posted & income)}


def _shape(t):
    return {"posted_cents": t["pe"] - t["pr"], "pending_cents": t["qe"] - t["qr"], "income_cents": t["inc"]}


def spending(user, workspace, start, end):
    """Net spending in cents for [start, end]: expenses minus refunds; transfers never count."""
    return _shape(visible_transactions(user, workspace).filter(posted_on__range=(start, end)).aggregate(**_sums()))


ZERO = {"posted_cents": 0, "pending_cents": 0, "income_cents": 0}


def daily(rows, start, end):
    """spending() per day of [start, end] for already-filtered visible rows: one grouped query, zero-filled,
    plus the running posted total (refunds can make a day negative and pull the line down)."""
    grouped = rows.filter(posted_on__range=(start, end)).values("posted_on").annotate(**_sums()).order_by()
    found = {r["posted_on"]: _shape(r) for r in grouped}
    days, running = [], 0
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        totals = found.get(day, ZERO)
        running += totals["posted_cents"]
        days.append({"day": day, **totals, "cumulative_cents": running})
    return days


def monthly(user, workspace, year):
    """spending() for each calendar month of the year, from one grouped query; empty months are zero."""
    rows = (visible_transactions(user, workspace).filter(posted_on__range=(date(year, 1, 1), date(year, 12, 31)))
            .annotate(m=ExtractMonth("posted_on")).values("m").annotate(**_sums()).order_by("m"))
    found = {r["m"]: _shape(r) for r in rows}
    return [{"month": date(year, m, 1), **found.get(m, ZERO)} for m in range(1, 13)]


def split_ids(workspace):
    return SplitLine.objects.filter(workspace=workspace).values("transaction_id")


def category_totals(rows, workspace, start, end):
    """{category id or None: {name, spending totals}} for already-filtered visible rows in [start, end].
    A split transaction counts each line in its category with the parent's classification and status;
    any other row counts in its overlay category. One grouped query plus one for split lines."""
    in_range = rows.filter(posted_on__range=(start, end))
    found = {r["ann__category"]: {"name": r["ann__category__name"] or "Uncategorized", **_shape(r)}
             for r in in_range.exclude(pk__in=split_ids(workspace)).values("ann__category", "ann__category__name").annotate(**_sums()).order_by()}
    parents = {r["pk"]: r for r in in_range.filter(pk__in=split_ids(workspace)).values("pk", "effective", "pending")}
    for line in SplitLine.objects.filter(workspace=workspace, transaction_id__in=list(parents)).select_related("category"):
        parent, totals = parents[line.transaction_id], found.setdefault(line.category_id, {"name": line.category.name, **ZERO})
        sign = {"expense": 1, "refund": -1}.get(parent["effective"], 0)
        totals["pending_cents" if parent["pending"] else "posted_cents"] += sign * line.amount_cents
        if parent["effective"] == "income" and not parent["pending"]:
            totals["income_cents"] += line.amount_cents
    return found


def by_category(rows, start, end, workspace):
    """category_totals() as a list, largest posted first; rows without a category are "Uncategorized" (id None)."""
    totals = [{"id": key, **t} for key, t in category_totals(rows, workspace, start, end).items()]
    return sorted((t for t in totals if t["posted_cents"] or t["pending_cents"]), key=lambda t: (-t["posted_cents"], t["name"]))


def period_bounds(kind, day):
    if kind == "year":
        return date(day.year, 1, 1), date(day.year, 12, 31)
    start = day.replace(day=1)
    return start, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def budget_progress(user, workspace, budgets, day):
    """Each budget's period containing `day`: posted net spending (refunds reduce it), pending as a separate
    estimate, remaining (negative when over) and whether posted spending is strictly above the limit."""
    rows = visible_transactions(user, workspace)
    result, per_period = [], {}
    for budget in budgets:
        start, end = period_bounds(budget.period, day)
        in_period = rows.filter(posted_on__range=(start, end))
        if budget.category_id:
            # Category totals once per period, shared by every category budget in it (splits count per line).
            if (start, end) not in per_period:
                per_period[start, end] = category_totals(rows, workspace, start, end)
            totals = per_period[start, end].get(budget.category_id, ZERO)
        else:
            # ponytail: one scan per name budget; name matches count whole transactions, splits do not apply.
            pattern, totals = normalize(budget.name_match), dict(ZERO)
            for row in in_period.filter(effective__in=("expense", "refund")).only("description", "amount_cents", "pending", "classification"):
                if pattern in normalize(row.description):
                    sign = 1 if row.effective == "expense" else -1
                    totals["pending_cents" if row.pending else "posted_cents"] += sign * row.amount_cents
        spent = totals["posted_cents"]
        result.append({"budget": budget, "start": start, "end": end, "spent_cents": spent, "pending_cents": totals["pending_cents"],
                       "remaining_cents": budget.limit_cents - spent, "over": spent > budget.limit_cents,
                       "share": min(100, max(0, round(100 * spent / budget.limit_cents))),
                       "paid": spent >= budget.limit_cents,  # fixed bills
                       "set_aside_monthly_cents": round(budget.limit_cents / 12),  # irregular costs
                       "set_aside_to_date_cents": budget.limit_cents * day.month // 12})
    return result


def monthly_equivalent(budget):
    return budget.limit_cents if budget.period == "month" else budget.limit_cents / 12


def disposable(user, workspace, day):
    """Estimated monthly plan: income - fixed bills - irregular set-asides = disposable; flexible budgets
    (monthly equivalents) are then compared against it. Income is the workspace's expected income, or the
    average posted income of the three complete months before `day`'s month. Everything here is an estimate."""
    if workspace.expected_income_cents is not None:
        income, source = workspace.expected_income_cents, "expected"
    else:
        end = day.replace(day=1) - timedelta(days=1)
        months = day.year * 12 + day.month - 1 - 3  # three complete months back
        start = date(months // 12, months % 12 + 1, 1)
        income, source = round(spending(user, workspace, start, end)["income_cents"] / 3), "average"
    totals = {"fixed": 0, "irregular": 0, "flexible": 0}
    for budget in workspace.budgets.all():
        totals[budget.kind] += monthly_equivalent(budget)
    fixed, set_aside, flexible = (round(totals[k]) for k in ("fixed", "irregular", "flexible"))
    return {"income_cents": income, "income_source": source, "fixed_cents": fixed, "set_aside_cents": set_aside,
            "disposable_cents": income - fixed - set_aside, "flexible_cents": flexible, "left_cents": income - fixed - set_aside - flexible}
