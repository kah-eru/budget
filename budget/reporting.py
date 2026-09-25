from datetime import date, timedelta

from django.db.models import F, FilteredRelation, Q, Sum
from django.db.models.functions import Coalesce, ExtractMonth

from .models import Transaction
from .permissions import visible_accounts


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


def by_category(rows, start, end):
    """spending() per category of this workspace for already-filtered visible rows, largest posted first;
    rows without a category are "Uncategorized" (id None). One grouped query; empty categories are skipped."""
    grouped = (rows.filter(posted_on__range=(start, end)).values("ann__category", "ann__category__name")
               .annotate(**_sums()).order_by())
    totals = [{"id": r["ann__category"], "name": r["ann__category__name"] or "Uncategorized", **_shape(r)} for r in grouped]
    return sorted((t for t in totals if t["posted_cents"] or t["pending_cents"]), key=lambda t: (-t["posted_cents"], t["name"]))
