"""Money moving between accounts, for the Timeline's Side by side layout."""
from collections import defaultdict
from datetime import timedelta
from itertools import groupby

WINDOW = timedelta(days=5)
LANE_LIMIT = 400


def pair(rows):
    """{out pk: in pk} for transfers (this workspace's type) that match one for one: another account, the same amount,
    opposite directions, at most 5 days apart. The closest dates pair first, then the oldest IDs. Only the rows passed
    in take part, so an account the viewer can't see is never a partner."""
    rows = [r for r in rows if r.effective == "transfer"]
    ins = defaultdict(list)
    for r in rows:
        if r.money_in:
            ins[r.amount_cents].append(r)
    # ponytail: pairs are recomputed per page; store them if people need to fix a wrong pair by hand.
    options = sorted((abs((o.posted_on - i.posted_on).days), o.pk, i.pk) for o in rows if not o.money_in for i in ins[o.amount_cents]
                     if o.account_id != i.account_id and abs(o.posted_on - i.posted_on) <= WINDOW)
    pairs, taken = {}, set()
    for _, out, into in options:
        if out not in pairs and into not in taken:
            pairs[out] = into
            taken.add(into)
    return pairs


def lanes(rows, accounts, candidates):
    """Day bands [(day, [(account, rows)])] for rows already newest first, one cell per lane, plus each lane's
    money in and out. candidates: the visible transfers around the range, which may hold partners not shown."""
    by_pk = {r.pk: r for r in candidates}
    partner = {}
    for out, into in pair(by_pk.values()).items():
        partner[out], partner[into] = by_pk[into], by_pk[out]
    for a in accounts:
        a.in_cents = a.out_cents = 0
    lane = {a.pk: a for a in accounts}  # every row's account has a lane
    for r in rows:
        r.partner = partner.get(r.pk)
        if r.money_in:
            lane[r.account_id].in_cents += r.amount_cents
        else:
            lane[r.account_id].out_cents += r.amount_cents
    bands = []
    for day, today in groupby(rows, key=lambda r: r.posted_on):
        cells = {a.pk: [] for a in accounts}
        for r in today:
            cells[r.account_id].append(r)
        bands.append((day, [(a, cells[a.pk]) for a in accounts]))
    return bands
