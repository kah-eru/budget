from datetime import date, timedelta

from django.db.models import F, FilteredRelation, Min, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

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


def _sums(amount="amount_cents"):
    def total(q):
        return Coalesce(Sum(amount, filter=q), 0)

    expense, refund, income = Q(effective="expense"), Q(effective="refund"), Q(effective="income")
    posted, pending = Q(pending=False), Q(pending=True)
    return {"pe": total(posted & expense), "pr": total(posted & refund), "qe": total(pending & expense), "qr": total(pending & refund), "inc": total(posted & income)}


def _shape(t):
    return {"posted_cents": t["pe"] - t["pr"], "pending_cents": t["qe"] - t["qr"], "income_cents": t["inc"]}


def spending(user, workspace, start, end):
    """Net spending in cents for [start, end]: expenses minus refunds; transfers never count."""
    return _shape(visible_transactions(user, workspace).filter(posted_on__range=(start, end)).aggregate(**_sums()))


ZERO = {"posted_cents": 0, "pending_cents": 0, "income_cents": 0}


def _steps(start, end, by_month):
    """Each day of [start, end], or the first of each month it touches."""
    if not by_month:
        return [start + timedelta(days=n) for n in range((end - start).days + 1)]
    steps, month = [], start.replace(day=1)
    while month <= end:
        steps.append(month)
        month = (month + timedelta(days=32)).replace(day=1)
    return steps


def _grouped(rows, start, end, by_month, sums):
    """{day, or first of the month: aggregated sums} for rows in [start, end], from one grouped query."""
    step = TruncMonth("posted_on") if by_month else F("posted_on")
    return {r["step"]: r for r in rows.filter(posted_on__range=(start, end)).annotate(step=step).values("step").annotate(**sums).order_by()}


def daily(rows, start, end, by_month=False, amount="amount_cents"):
    """spending() per day of [start, end] (or per month) for already-filtered visible rows: one grouped query,
    zero-filled, plus the running posted total (refunds can make a day negative and pull the line down)."""
    found = {k: _shape(r) for k, r in _grouped(rows, start, end, by_month, _sums(amount)).items()}
    days, running = [], 0
    for day in _steps(start, end, by_month):
        totals = found.get(day, ZERO)
        running += totals["posted_cents"]
        days.append({"day": day, **totals, "cumulative_cents": running})
    return days


def by_year(months):
    """daily(..., by_month=True) summed per calendar year (Lifetime's table)."""
    years = {}
    for m in months:
        year = years.setdefault(m["day"].year, {"day": date(m["day"].year, 1, 1), **ZERO})
        for key in ZERO:
            year[key] += m[key]
    return list(years.values())


def first_day(user, workspace):
    """Lifetime's start: the earliest transaction this user can see here, or today."""
    today = timezone.localdate()
    first = Transaction.objects.filter(account__in=visible_accounts(user, workspace)).aggregate(d=Min("posted_on"))["d"]
    return min(first or today, today)


def split_ids(workspace):
    return SplitLine.objects.filter(workspace=workspace).values("transaction_id")


def category_share(rows, workspace, category_id):
    """rows with `share`: what each counts toward this category here. A split row counts only its lines in the
    category (the Budget tab's rule); any other row counts in full. Sum `share` instead of amount_cents."""
    lines = (SplitLine.objects.filter(workspace=workspace, category_id=category_id, transaction=OuterRef("pk"))
             .values("transaction").annotate(total=Sum("amount_cents")).values("total"))
    return rows.annotate(share=Coalesce(Subquery(lines), F("amount_cents")))


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


def budget_progress(user, workspace, budgets, day, span=None):
    """Each budget's period containing `day`: posted net spending (refunds reduce it), pending as a separate
    estimate, remaining (negative when over) and whether posted spending is strictly above the limit.
    span: a whole year for the Overview's Year view, where a monthly budget counts 12 times its limit."""
    rows = visible_transactions(user, workspace)
    budgets = list(budgets)
    periods = []
    for budget in budgets:
        start, end = period_bounds(budget.period, day)
        limit = budget.limit_cents
        if span and budget.period == "month":
            (start, end), limit = span, limit * 12
        periods.append((start, end, limit))
    per_period, by_name = {}, {}
    for (start, end, _), budget in zip(periods, budgets):
        if budget.category_id and (start, end) not in per_period:
            # Category totals once per period, shared by every category budget in it (splits count per line).
            per_period[start, end] = category_totals(rows, workspace, start, end)
        elif not budget.category_id:
            by_name.setdefault((start, end), set()).add(normalize(budget.name_match))
    for (start, end), patterns in by_name.items():
        # One scan per period for every name budget in it; name matches count whole transactions, splits do not apply.
        found = {p: dict(ZERO) for p in patterns}
        scan = rows.filter(posted_on__range=(start, end), effective__in=("expense", "refund")).values_list("description", "amount_cents", "pending", "effective")
        for description, cents, pending, effective in scan:
            text = normalize(description)
            for pattern in patterns:
                if pattern in text:
                    found[pattern]["pending_cents" if pending else "posted_cents"] += cents if effective == "expense" else -cents
        by_name[start, end] = found
    result = []
    for (start, end, limit), budget in zip(periods, budgets):
        if budget.category_id:
            totals = per_period[start, end].get(budget.category_id, ZERO)
        else:
            totals = by_name[start, end][normalize(budget.name_match)]
        spent = totals["posted_cents"]
        result.append({"budget": budget, "start": start, "end": end, "limit_cents": limit, "spent_cents": spent, "pending_cents": totals["pending_cents"],
                       "remaining_cents": limit - spent, "over": spent > limit,
                       "share": min(100, max(0, round(100 * spent / limit))),
                       "paid": spent >= limit,  # fixed bills
                       "set_aside_monthly_cents": round(budget.limit_cents / 12),  # irregular costs
                       "set_aside_to_date_cents": budget.limit_cents * day.month // 12})
    return result


def _flows(amount="amount_cents"):
    return {"i": Coalesce(Sum(amount, filter=Q(money_in=True)), 0), "o": Coalesce(Sum(amount, filter=Q(money_in=False)), 0)}


def saved_daily(rows, start, end, by_month=False, amount="amount_cents"):
    """Net saved per day of [start, end] (or per month) for rows already limited to savings accounts: posted only, money
    in minus money out by the bank's direction, zero-filled, with the running net from `start`."""
    found = _grouped(rows.filter(pending=False), start, end, by_month, _flows(amount))
    days, running = [], 0
    for day in _steps(start, end, by_month):
        r = found.get(day, {"i": 0, "o": 0})
        running += r["i"] - r["o"]
        days.append({"day": day, "in_cents": r["i"], "out_cents": r["o"], "posted_cents": r["i"] - r["o"], "cumulative_cents": running})
    return days


def savings(user, workspace, start, end):
    """Money in and out of the savings accounts this user can see here, posted only, by the bank's direction: a transfer to
    checking is money out and interest is money in, while a move between two savings accounts nets out. Moving money is
    never spending; spending() counts it only once it's spent. cumulative_cents is the running net saved from `start`,
    because the chart's scale starts at zero. balance_cents sums the last known balances."""
    accounts = list(visible_accounts(user, workspace).filter(is_savings=True).select_related("owner").order_by("name", "pk"))
    rows = Transaction.objects.filter(account__in=accounts, pending=False, posted_on__range=(start, end))
    per_account = {r["account"]: r for r in rows.values("account").annotate(**_flows()).order_by()}
    for a in accounts:
        r = per_account.get(a.pk, {"i": 0, "o": 0})
        a.in_cents, a.out_cents, a.net_cents = r["i"], r["o"], r["i"] - r["o"]
    days, months = saved_daily(rows, start, end), saved_daily(rows, start, end, by_month=True)
    known = [a for a in accounts if a.balance_cents is not None]
    total_in, total_out = sum(a.in_cents for a in accounts), sum(a.out_cents for a in accounts)
    return {"accounts": accounts, "in_cents": total_in, "out_cents": total_out, "net_cents": total_in - total_out, "days": days, "months": months,
            "balance_cents": sum(a.balance_cents for a in known), "unknown": len(accounts) - len(known)}


def saved_net(user, workspace, start, end):
    """savings()["net_cents"] alone, in one query: the previous period's comparison needs nothing else."""
    t = Transaction.objects.filter(account__in=visible_accounts(user, workspace).filter(is_savings=True), pending=False,
                                   posted_on__range=(start, end)).aggregate(**_flows())
    return t["i"] - t["o"]


def net_worth(user, workspace):
    """What's owned minus what's owed, from last known balances. A group sees only accounts shared with it."""
    accounts = list(visible_accounts(user, workspace).select_related("owner").order_by("name", "pk"))
    counted = [a for a in accounts if a.balance_kind and a.balance_cents is not None]
    assets = [a for a in counted if a.balance_kind == "asset"]
    debts = [a for a in counted if a.balance_kind == "liability"]
    own, owe = sum(a.balance_cents for a in assets), sum(a.balance_cents for a in debts)
    return {"assets": assets, "debts": debts, "uncounted": [a for a in accounts if not (a.balance_kind and a.balance_cents is not None)],
            "own_cents": own, "owe_cents": owe, "net_cents": own - owe}


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
