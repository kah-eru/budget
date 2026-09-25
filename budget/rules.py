from django.db.models import Q

from .models import Rule, SplitLine, TransactionAnnotation, Workspace


def normalize(text):
    return " ".join(text.split()).casefold()


def matches(rule, description):
    text, pattern = normalize(description), normalize(rule.pattern)
    return text == pattern if rule.kind == "exact" else pattern in text


def suggest_keyword(description):
    """A starting keyword from a bank name: drop store numbers and codes (words starting with # or at least
    half digits, so 7-ELEVEN stays), keep the first three words."""
    words = [w for w in description.split() if not w.startswith("#") and sum(c.isdigit() for c in w) * 2 < len(w)]
    return " ".join(words[:3])


def ensure_rule(workspace, keyword, category):
    """A 'name contains' rule for keyword -> category, unless an enabled equivalent already exists."""
    keyword = " ".join(keyword.split())
    for rule in Rule.objects.filter(workspace=workspace, category=category, kind="contains", enabled=True):
        if normalize(rule.pattern) == normalize(keyword):
            return rule
    return Rule.objects.create(workspace=workspace, kind="contains", pattern=keyword, category=category)


def largest_remainder(total, percents):
    """Split integer cents by whole percentages (summing to 100) so the parts add up exactly: floor each share,
    then give the leftover cents to the largest fractional remainders (earlier lines win ties)."""
    raw = [total * p for p in percents]  # hundredths of a cent
    parts = [r // 100 for r in raw]
    for i in sorted(range(len(parts)), key=lambda i: (-(raw[i] % 100), i))[:total - sum(parts)]:
        parts[i] += 1
    return parts


def drop_rule_splits(workspace, transaction_ids):
    """A hand-picked category replaces any split a rule wrote for these rows."""
    SplitLine.objects.filter(workspace=workspace, transaction__in=transaction_ids, from_rule=True).delete()


def categorize(transactions, workspace):
    """Set the rule category in this workspace's overlay for each transaction; manual choices are never changed.
    Rows no rule matches lose an earlier rule category. A rule with a split template also (re)writes the row's
    rule split lines; a hand-made split counts as a manual choice. Returns how many rows changed."""
    rules = list(Rule.objects.filter(workspace=workspace, enabled=True, category__archived=False)
                 .exclude(split_category__archived=True).order_by("priority", "pk"))
    transactions = list(transactions)
    ids = [t.pk for t in transactions]
    existing = {a.transaction_id: a for a in TransactionAnnotation.objects.filter(workspace=workspace, transaction__in=ids)}
    lines = SplitLine.objects.filter(workspace=workspace, transaction__in=ids)
    hand_split = set(lines.filter(from_rule=False).values_list("transaction_id", flat=True))
    rule_lines = {}
    for line in lines.filter(from_rule=True):
        rule_lines.setdefault(line.transaction_id, set()).add((line.category_id, line.amount_cents))
    created, updated, stale, new_lines = [], [], [], []
    for row in transactions:
        annotation = existing.get(row.pk)
        if row.pk in hand_split or (annotation and annotation.category_source == "manual"):
            continue
        rule = next((r for r in rules if matches(r, row.description)), None)
        category_id = rule.category_id if rule else None
        wanted = []  # in template order, so the first category is listed first
        if rule and rule.split_category_id:
            amounts = largest_remainder(row.amount_cents, [100 - rule.split_percent, rule.split_percent])
            wanted = [(c, a) for c, a in zip((rule.category_id, rule.split_category_id), amounts) if a > 0]
        if set(wanted) != rule_lines.get(row.pk, set()):
            stale.append(row.pk)
            new_lines += [SplitLine(transaction=row, workspace=workspace, category_id=c, amount_cents=a, from_rule=True) for c, a in wanted]
        if annotation is None:
            if category_id:
                created.append(TransactionAnnotation(transaction=row, workspace=workspace, category_id=category_id, category_source="rule"))
        elif annotation.category_id != category_id:
            annotation.category_id, annotation.category_source = category_id, "rule" if category_id else ""
            updated.append(annotation)
    TransactionAnnotation.objects.bulk_create(created)
    TransactionAnnotation.objects.bulk_update(updated, ["category", "category_source"])
    drop_rule_splits(workspace, stale)
    SplitLine.objects.bulk_create(new_lines)
    return len({a.transaction_id for a in created + updated} | set(stale))


def categorize_everywhere(row):
    """A new or edited transaction gets the current rules of every workspace that can see its account."""
    account = row.account
    for workspace in Workspace.objects.filter(Q(owner_id=account.owner_id, is_personal=True) | Q(account_shares__account=account)).distinct():
        categorize([row], workspace)
