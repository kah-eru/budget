"""Plaid bank sync: the only module that talks to Plaid. Tokens are encrypted at rest; payloads and tokens are never logged."""
import json
from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import plaid as sdk
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from plaid.api import plaid_api
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from urllib3.exceptions import HTTPError

from .models import BankConnection, Transaction
from .notifications import evaluate_account
from .rules import categorize_everywhere
from .sharing import bump_account_data

# ponytail: one sync a minute per connection doubles as the in-request lock; a crashed sync frees after it. Real leases come with worker jobs.
COOLDOWN = timedelta(seconds=60)
MUTATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"
TRANSFERS = ("TRANSFER_IN", "TRANSFER_OUT", "LOAN_PAYMENTS")  # card payments and moves between accounts are never spending
UPDATED = ["account", "provider_id", "posted_on", "amount_cents", "classification", "pending", "description", "provider_category"]


class PlaidError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def enabled():
    return bool(settings.PLAID_CLIENT_ID and settings.PLAID_SECRET and settings.PLAID_TOKEN_KEY)


def encrypt(token):
    return Fernet(settings.PLAID_TOKEN_KEY.encode()).encrypt(token.encode()).decode()


def decrypt(token):
    try:
        return Fernet(settings.PLAID_TOKEN_KEY.encode()).decrypt(token.encode()).decode()
    except InvalidToken:  # PLAID_TOKEN_KEY was replaced: the bank has to be connected again
        raise PlaidError("TOKEN_KEY_CHANGED") from None


def _call(method, request):
    host = sdk.Environment.Production if settings.PLAID_ENV == "production" else sdk.Environment.Sandbox
    api = plaid_api.PlaidApi(sdk.ApiClient(sdk.Configuration(host=host, api_key={"clientId": settings.PLAID_CLIENT_ID, "secret": settings.PLAID_SECRET})))
    try:
        return getattr(api, method)(request)
    except sdk.ApiException as error:
        try:
            code = json.loads(error.body or "{}").get("error_code")
        except ValueError:
            code = None
        raise PlaidError(code or f"HTTP_{error.status}") from None
    except (HTTPError, OSError):
        raise PlaidError("CONNECTION_FAILED") from None


def link_token(user):
    return _call("link_token_create", LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=str(user.pk)), client_name="Budget", products=[Products("transactions")],
        transactions=LinkTokenTransactions(days_requested=730), country_codes=[CountryCode("US")], language="en")).link_token


def exchange(public_token):
    response = _call("item_public_token_exchange", ItemPublicTokenExchangeRequest(public_token=public_token))
    return response.access_token, response.item_id


def accounts(connection):
    response = _call("accounts_get", AccountsGetRequest(access_token=decrypt(connection.access_token)))
    return [{"id": a.account_id, "name": a.name, "mask": a.mask or "", "type": str(a.type.value), "subtype": str(a.subtype.value) if a.subtype else ""}
            for a in response.accounts]


def remove(connection):
    _call("item_remove", ItemRemoveRequest(access_token=decrypt(connection.access_token)))


def _txn(t):
    category = t.personal_finance_category.detailed if t.personal_finance_category else ""
    return {"id": t.transaction_id, "account": t.account_id, "amount": Decimal(str(t.amount)), "currency": t.iso_currency_code,
            "date": t.date, "name": t.name or "", "pending": bool(t.pending), "pending_id": t.pending_transaction_id, "category": category or ""}


def _page(token, cursor):
    request = TransactionsSyncRequest(access_token=token, count=500, **({"cursor": cursor} if cursor else {}))
    response = _call("transactions_sync", request)
    return {"added": [_txn(t) for t in response.added], "modified": [_txn(t) for t in response.modified],
            "removed": [r.transaction_id for r in response.removed], "next_cursor": response.next_cursor, "has_more": response.has_more,
            "status": getattr(response.transactions_update_status, "value", "")}


def fetch(connection):
    """Every page since the committed cursor, collected before anything is saved. Plaid asks for a restart from
    the committed cursor when data changes mid-pagination."""
    token = decrypt(connection.access_token)
    for _ in range(3):
        added, modified, removed, cursor = [], [], [], connection.cursor
        try:
            while True:
                page = _page(token, cursor)
                added += page["added"]
                modified += page["modified"]
                removed += page["removed"]
                cursor = page["next_cursor"]
                if not page["has_more"]:
                    return added, modified, removed, cursor, page["status"]
        except PlaidError as error:
            if error.code != MUTATION:
                raise
    raise PlaidError(MUTATION)


def classify(amount, category):
    """Plaid's positive amount is money out."""
    if category.startswith(TRANSFERS):
        return "transfer"
    if amount > 0:
        return "expense"
    return "income" if category.startswith("INCOME") else "refund"


def _fields(t):
    cents = int((abs(t["amount"]) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return {"posted_on": t["date"], "amount_cents": cents, "classification": classify(t["amount"], t["category"]), "pending": t["pending"],
            "description": t["name"][:200], "provider_category": t["category"][:100]}


def _apply(connection, added, modified, removed):
    """Returns the rows written, by account. A posted row that replaces a pending one takes over the pending row itself,
    so its names, categories, notes and splits carry over and it counts once."""
    by_provider = {a.provider_account_id: a for a in connection.accounts.all()}
    ids = {t["id"] for t in added + modified} | {t["pending_id"] for t in added if t["pending_id"]}
    existing = {r.provider_id: r for r in Transaction.objects.filter(account__connection=connection, provider_id__in=ids)}
    touched, new, changed = defaultdict(dict), [], {}
    for t in added + modified:
        account = by_provider.get(t["account"])
        if account is None or t["currency"] != "USD" or not t["amount"]:
            continue  # not imported, not USD (the app is USD-only), or zero
        row = existing.get(t["id"]) or (existing.pop(t["pending_id"], None) if t["pending_id"] else None)
        if row is None:
            row = Transaction(account=account)
            new.append(row)
        for name, value in {**_fields(t), "account": account, "provider_id": t["id"]}.items():
            setattr(row, name, value)
        if row.pk:
            changed[row.pk] = row
        existing[t["id"]] = row
        touched[account][id(row)] = row
    # The replaced pending row still has its old ID in the database, so it is kept out of the removals.
    gone = Transaction.objects.filter(account__connection=connection, provider_id__in=removed).exclude(pk__in=list(changed))
    for account in {r.account for r in gone.select_related("account")}:
        touched.setdefault(account, {})
    gone.delete()
    Transaction.objects.bulk_update(list(changed.values()), UPDATED)
    Transaction.objects.bulk_create(new)
    return {account: list(rows.values()) for account, rows in touched.items()}


def sync(connection):
    """Returns ("ok" | "busy" | "error", rows written). The cursor and the changes it covers commit together."""
    now = timezone.now()
    claimed = BankConnection.objects.filter(pk=connection.pk).filter(Q(sync_started_at=None) | Q(sync_started_at__lt=now - COOLDOWN))
    if not claimed.update(sync_started_at=now):
        return "busy", 0
    connection.refresh_from_db()
    started_from = connection.cursor
    try:
        added, modified, removed, cursor, status = fetch(connection)
    except PlaidError as error:
        BankConnection.objects.filter(pk=connection.pk).update(status="error", error_code=error.code[:60])
        return "error", 0
    with transaction.atomic():
        locked = BankConnection.objects.select_for_update().get(pk=connection.pk)
        if locked.cursor != started_from:
            return "busy", 0  # another sync committed these pages first
        touched = _apply(locked, added, modified, removed)
        locked.cursor, locked.last_synced_at, locked.status, locked.error_code = cursor, timezone.now(), "ok", ""
        locked.history_ready = locked.history_ready or status in ("INITIAL_UPDATE_COMPLETE", "HISTORICAL_UPDATE_COMPLETE")
        locked.save()
        for account, rows in touched.items():
            categorize_everywhere(rows)
            bump_account_data(account)
            evaluate_account(account)
    return "ok", sum(len(rows) for rows in touched.values())
