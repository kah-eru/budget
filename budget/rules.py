from django.db.models import Q

from .models import Rule, TransactionAnnotation, Workspace


def normalize(text):
    return " ".join(text.split()).casefold()


def matches(rule, description):
    text, pattern = normalize(description), normalize(rule.pattern)
    return text == pattern if rule.kind == "exact" else pattern in text


def categorize(transactions, workspace):
    """Set the rule category in this workspace's overlay for each transaction; manual choices are never changed.
    Rows no rule matches lose an earlier rule category. Returns how many annotations changed."""
    rules = list(Rule.objects.filter(workspace=workspace, enabled=True, category__archived=False).order_by("priority", "pk"))
    transactions = list(transactions)
    existing = {a.transaction_id: a for a in TransactionAnnotation.objects.filter(workspace=workspace, transaction__in=[t.pk for t in transactions])}
    created, updated = [], []
    for row in transactions:
        annotation = existing.get(row.pk)
        if annotation and annotation.category_source == "manual":
            continue
        category_id = next((r.category_id for r in rules if matches(r, row.description)), None)
        if annotation is None:
            if category_id:
                created.append(TransactionAnnotation(transaction=row, workspace=workspace, category_id=category_id, category_source="rule"))
        elif annotation.category_id != category_id:
            annotation.category_id, annotation.category_source = category_id, "rule" if category_id else ""
            updated.append(annotation)
    TransactionAnnotation.objects.bulk_create(created)
    TransactionAnnotation.objects.bulk_update(updated, ["category", "category_source"])
    return len(created) + len(updated)


def categorize_everywhere(row):
    """A new or edited transaction gets the current rules of every workspace that can see its account."""
    account = row.account
    for workspace in Workspace.objects.filter(Q(owner_id=account.owner_id, is_personal=True) | Q(account_shares__account=account)).distinct():
        categorize([row], workspace)
