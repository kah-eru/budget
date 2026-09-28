"""CSV import: parse with the owner's column mapping, flag rows that look already imported, save all rows or none."""
import csv
import io
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction

from .models import ImportBatch, Transaction, TransactionAnnotation
from .notifications import evaluate_account
from .rules import categorize_everywhere, normalize
from .sharing import bump_account_data

# ponytail: synchronous with these caps; move to the milestone 3 worker jobs for bigger files.
MAX_BYTES, MAX_ROWS = 1024 * 1024, 5000
# ponytail: US and ISO dates only (a USD app); add a format picker if a DD/MM file shows up.
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y/%m/%d")
GUESSES = {"date_col": ("date", "posted"), "description_col": ("description", "payee", "name", "memo"),
           "amount_col": ("amount", "debit"), "credit_col": ("credit",), "category_col": ("category",)}


def decode(raw):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return text.replace("\x00", "")  # PostgreSQL text can't hold NUL


def rows(text):
    """Every record, blank ones included, so list position + 1 is the spreadsheet row number."""
    return list(csv.reader(io.StringIO(text, newline="")))


def filled(records):
    return sum(1 for r in records if any(c.strip() for c in r))


def _date(value, fmt):
    try:
        return datetime.strptime(value.split()[0], fmt).date()  # drops a time part such as "00:00:00"
    except (ValueError, IndexError):
        return None


def has_header(first):
    return not any(_date(c.strip(), f) for c in first for f in DATE_FORMATS)


def cents(value):
    text = value.strip().replace("$", "").replace(",", "")
    negative = text.startswith("(") and text.endswith(")")  # accounting style (12.00)
    try:
        amount = Decimal(text.strip("()") or "0")
    except InvalidOperation:
        raise ValueError(f"“{value}” isn't an amount")
    if not amount.is_finite() or abs(amount) >= 10 ** 10:
        raise ValueError(f"“{value}” isn't an amount")
    amount *= 100
    if amount != amount.to_integral_value():
        raise ValueError(f"“{value}” has a fraction of a cent")
    return -int(amount) if negative else int(amount)


def _cell(record, col):
    return record[col].strip() if col is not None and col < len(record) else ""


def guess(header, data):
    """Default mapping from column names; the sign is whichever most amounts have, since most rows are spending."""
    names = [h.strip().lower() for h in header]
    found = {}
    for field, words in GUESSES.items():
        found[field] = next((i for w in words for i, n in enumerate(names) if w in n and i not in found.values()), None)
    for field, default in (("date_col", 0), ("description_col", 1), ("amount_col", 2)):
        if found[field] is None:
            found[field] = default
    signs = Counter()
    for record in data[:200]:
        try:
            signs[cents(_cell(record, found["amount_col"])) > 0] += 1
        except ValueError:
            pass
    return {**found, "sign": "negative" if signs[False] >= signs[True] else "positive", "incoming": "income"}


def parse(records, m):
    """Returns (rows, errors, zero rows skipped). Each row is ready to save; money out is an expense."""
    start = 1 if m["header"] else 0
    data = [(n, r) for n, r in enumerate(records[start:], start + 1) if any(c.strip() for c in r)]
    fmt = max(DATE_FORMATS, key=lambda f: sum(_date(_cell(r, m["date_col"]), f) is not None for _, r in data))
    parsed, errors, skipped = [], [], 0
    for n, r in data:
        try:
            posted_on = _date(_cell(r, m["date_col"]), fmt)
            if posted_on is None:
                raise ValueError(f"“{_cell(r, m['date_col'])}” isn't a date like {date(2026, 5, 1):{fmt}}")
            if m["credit_col"] is None:
                out = cents(_cell(r, m["amount_col"]))
                out = -out if m["sign"] == "negative" else out
            else:
                paid, received = cents(_cell(r, m["amount_col"])), cents(_cell(r, m["credit_col"]))
                if paid and received:
                    raise ValueError("both money out and money in are filled")
                out = abs(paid) or -abs(received)
        except ValueError as error:
            errors.append(f"Row {n}: {error}.")
            continue
        if not out:
            skipped += 1
            continue
        parsed.append({"source_row": n, "posted_on": posted_on, "description": _cell(r, m["description_col"])[:200],
                       "amount_cents": abs(out), "classification": "expense" if out > 0 else m["incoming"], "money_in": out < 0,
                       "category": _cell(r, m["category_col"])})
    return parsed, errors, skipped


def overlaps(account, parsed):
    """Rows that look already in the account (same date, amount and name). Counted, not merged: with one $4.50
    coffee already there, a file holding two flags only one, so a second real purchase is kept."""
    if not parsed:
        return set()
    days = [p["posted_on"] for p in parsed]
    existing = Counter((d, c, normalize(t)) for d, c, t in account.transactions.filter(posted_on__range=(min(days), max(days)))
                       .values_list("posted_on", "amount_cents", "description"))
    flagged = set()
    for p in parsed:
        key = (p["posted_on"], p["amount_cents"], normalize(p["description"]))
        if existing[key]:
            existing[key] -= 1
            flagged.add(p["source_row"])
    return flagged


def commit(batch, parsed, keep, workspace):
    """Saves every chosen row or none. Returns (imported, skipped), or None when this file is already imported."""
    try:
        with transaction.atomic():
            batch = ImportBatch.objects.select_for_update().select_related("account").filter(pk=batch.pk, status="preview").first()
            if batch is None:
                return None
            skip = overlaps(batch.account, parsed) - set(keep)
            chosen = [p for p in parsed if p["source_row"] not in skip]
            new = Transaction.objects.bulk_create([Transaction(account=batch.account, import_batch=batch, **{k: p[k] for k in (
                "source_row", "posted_on", "description", "amount_cents", "classification", "money_in")}) for p in chosen])
            # A category column counts as the owner's choice, in the workspace the import was started from.
            categories = {c.name.casefold(): c for c in workspace.categories.filter(archived=False)}
            TransactionAnnotation.objects.bulk_create([
                TransactionAnnotation(transaction=row, workspace=workspace, category=categories[p["category"].casefold()], category_source="manual")
                for row, p in zip(new, chosen) if p["category"].casefold() in categories])
            batch.status, batch.row_count, batch.content = "done", len(new), ""
            batch.save()  # the same file already imported fails here, before any rule or budget work
            categorize_everywhere(new)
            bump_account_data(batch.account)
            evaluate_account(batch.account)
    except IntegrityError:
        return None
    return len(new), len(skip)
