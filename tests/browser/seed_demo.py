"""Made-up demo data for the browser-check user in the local preview database (.local/browser.sqlite3). Never personal data.

Run: .venv/Scripts/python tests/browser/seed_demo.py [--reset]
Six months of accounts of every kind, with paired transfers (checking to savings, card and loan payments), budgets and categories.
"""
import os
import random
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="1", BUDGET_LOCAL_SQLITE="1", DJANGO_SECRET_KEY=secrets.token_urlsafe(48))

import django
from django.conf import settings

settings.DATABASES["default"]["NAME"] = ROOT / ".local" / "browser.sqlite3"
django.setup()

from django.db import transaction
from django.utils import timezone

from budget.models import Account, Budget, Category, Transaction, TransactionAnnotation, User, Workspace
from budget.sharing import bump_account_data

user = User.objects.get(username="browser-check")
personal = Workspace.objects.get(owner=user, is_personal=True)
if "--reset" in sys.argv:
    Account.objects.filter(owner=user, name__startswith="Demo ").delete()
if Account.objects.filter(owner=user, name__startswith="Demo ").exists():
    sys.exit("Already seeded. Use --reset to seed again.")

rng = random.Random(7)
today = timezone.localdate()
first = (today.replace(day=1) - timedelta(days=150)).replace(day=1)
now = timezone.now()


def account(name, kind="", balance=None, savings=False):
    return Account.objects.create(owner=user, name=name, balance_kind=kind, balance_cents=balance, is_savings=savings,
                                  balance_updated_at=now if balance is not None else None)


categories = {c.name: c for c in personal.categories.all()}
rows, labels = [], []


def add(acct, day, dollars, description, classification="expense", money_in=None, category=None, pending=False):
    if day > today:
        return None
    row = Transaction(account=acct, posted_on=day, amount_cents=round(dollars * 100), description=description, classification=classification,
                      money_in=classification in ("income", "refund") if money_in is None else money_in, pending=pending)
    rows.append(row)
    if category:
        labels.append((row, categories[category]))
    return row


def move(source, target, day, dollars, out_name, in_name, lag=0):
    """A transfer: out of one account and into another, so the Timeline's List view joins them."""
    add(source, day, dollars, out_name, "transfer", money_in=False)
    add(target, day + timedelta(days=lag), dollars, in_name, "transfer", money_in=True)


with transaction.atomic():
    checking = account("Demo Checking ••4821", "asset", 425000)
    savings = account("Demo Savings ••9910", "asset", 1240000, savings=True)
    high_yield = account("Demo High-Yield Savings ••3307", "asset", 815000, savings=True)
    card = account("Demo Credit Card ••7702", "liability", 128437)
    loan = account("Demo Car Loan ••5520", "liability", 1420000)
    brokerage = account("Demo Brokerage ••6614", "asset", 3890000)
    account("Demo Home (estimate)", "asset", 42000000)
    wallet = account("Demo Cash Wallet")

    month = first
    while month <= today:
        d = lambda n: month.replace(day=min(n, 28))
        add(checking, d(1), 2650, "ACME Corp Payroll", "income")
        add(checking, d(15), 2650, "ACME Corp Payroll", "income")
        add(checking, d(1), 1800, "Oakwood Apartments Rent", category="Housing")
        add(checking, d(5), rng.uniform(85, 140), "City Power & Light", category="Utilities")
        add(checking, d(12), 65, "Fiberlink Internet", category="Utilities")
        add(checking, d(18), 45, "Mobile Co Wireless", category="Utilities")
        move(checking, brokerage, d(2), 250, "Transfer to Brokerage", "Contribution from Checking", lag=1)
        move(checking, savings, d(16), 500, "Transfer to Savings", "Transfer from Checking")
        move(checking, loan, d(20), 385, "Car Loan Payment", "Payment received", lag=1)
        move(checking, card, d(25), round(rng.uniform(900, 1300), 2), "Credit Card Payment", "Payment - Thank you", lag=2)
        move(savings, high_yield, d(21), 200, "Transfer to High-Yield", "Transfer from Savings")
        if month.month % 3 == 0:
            move(savings, checking, d(9), 300, "Transfer to Checking", "Transfer from Savings")
            move(checking, wallet, d(10), 100, "ATM Withdrawal", "Cash from ATM")
        add(savings, d(28), rng.uniform(8, 14), "Interest Payment", "income")
        add(high_yield, d(28), rng.uniform(24, 32), "Interest Payment", "income")
        add(card, d(8), 15.49, "Netflix", category="Subscriptions")
        add(card, d(11), 11.99, "Spotify", category="Subscriptions")
        for week in range(4):
            add(card, d(3 + 7 * week), rng.uniform(60, 160), rng.choice(["FreshMart", "Green Grocer"]), category="Groceries")
            add(card, d(6 + 7 * week), rng.uniform(35, 60), "QuickFuel", category="Transport")
            for _ in range(rng.randint(1, 3)):
                add(card, d(rng.randint(1, 28)), rng.uniform(12, 65), rng.choice(["Cafe Luna", "Taco Stand", "Noodle House", "Pizza Corner"]), category="Dining")
        add(card, d(rng.randint(1, 28)), rng.uniform(20, 120), "Homegoods Store", category="Shopping")
        add(wallet, d(rng.randint(10, 28)), rng.uniform(8, 25), "Farmers Market", category="Groceries")
        month = (month + timedelta(days=32)).replace(day=1)
    add(card, today.replace(day=max(1, today.day - 3)), 42, "Homegoods Store Refund", "refund", category="Shopping")
    add(card, today, 23.75, "Noodle House", category="Dining", pending=True)
    add(card, today, 61.20, "FreshMart", category="Groceries", pending=True)

    Transaction.objects.bulk_create(rows)
    TransactionAnnotation.objects.bulk_create(TransactionAnnotation(transaction=row, workspace=personal, category=category, category_source="manual")
                                              for row, category in labels)
    for category, kind, period, limit, due in (("Groceries", "flexible", "month", 60000, None), ("Dining", "flexible", "month", 25000, None),
                                                ("Housing", "fixed", "month", 180000, 1), ("Subscriptions", "flexible", "month", 4000, None),
                                                ("Travel", "irregular", "year", 240000, None)):
        if not Budget.objects.filter(workspace=personal, category=categories[category], period=period).exists():  # test runs may have made one
            Budget.objects.create(workspace=personal, category=categories[category], period=period, kind=kind, limit_cents=limit, due_day=due)
    for a in (checking, savings, high_yield, card, loan, brokerage, wallet):
        bump_account_data(a)

print(f"Seeded {len(rows)} transactions in 8 demo accounts, {first:%b %Y} to {today:%b %d, %Y}.")
