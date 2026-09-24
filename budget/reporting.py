from django.db.models import F, FilteredRelation, Q, Sum
from django.db.models.functions import Coalesce

from .models import Transaction
from .permissions import visible_accounts


def annotated(transactions, workspace):
    """Attach this workspace's overlay only: ann_name, ann_note and effective classification."""
    return transactions.annotate(
        ann=FilteredRelation("annotations", condition=Q(annotations__workspace=workspace)),
        ann_name=F("ann__display_name"), ann_note=F("ann__note"),
        effective=Coalesce("ann__classification", "classification"),
    )


def spending(user, workspace, start, end):
    """Net spending in cents for [start, end]: expenses minus refunds; transfers never count."""
    rows = annotated(Transaction.objects.filter(account__in=visible_accounts(user, workspace), posted_on__range=(start, end)), workspace)

    def total(q):
        return Coalesce(Sum("amount_cents", filter=q), 0)

    expense, refund, income = Q(effective="expense"), Q(effective="refund"), Q(effective="income")
    posted, pending = Q(pending=False), Q(pending=True)
    t = rows.aggregate(
        pe=total(posted & expense), pr=total(posted & refund), qe=total(pending & expense), qr=total(pending & refund), inc=total(posted & income),
    )
    return {"posted_cents": t["pe"] - t["pr"], "pending_cents": t["qe"] - t["qr"], "income_cents": t["inc"]}
