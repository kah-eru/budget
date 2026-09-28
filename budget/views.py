import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from smtplib import SMTPException
from urllib.parse import quote, urlencode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from . import flows
from . import imports
from . import recurring
from .goals import progress as goal_progress
from . import plaid as bank
from .account_mail import UNSUBSCRIBE_SALT, notify
from .forms import (
    AccountForm, AnnotationForm, BudgetForm, CategoryForm, EmailChangeForm, GoalForm, GroupForm, ImportMappingForm, ImportUploadForm, IncomeForm, RecurringForm, RuleForm, SplitForm, SharingForm, TransactionFilterForm, TransactionForm, UsernameChangeForm,
)
from .invitations import claim_email_send
from .models import Account, BankConnection, BillReminder, Budget, BudgetAlert, Category, Goal, Recurring, Membership, MembershipNotice, PushSubscription, Rule, SplitLine, Transaction, TransactionAnnotation, User, Workspace
from .permissions import editable_accounts, get_workspace, visible_accounts, visible_workspaces
from .reporting import _shape, _sums, annotated, budget_progress, by_category, by_year, disposable, daily, first_day, net_worth, period_bounds, saved_daily, savings, spending, visible_transactions
from .notifications import evaluate, evaluate_account
from . import push
from .rules import categorize, categorize_everywhere, drop_rule_splits, ensure_rule, matches, normalize
from .templatetags.money import dollars
from .sharing import bump_account_data, remove_member, replace_shares


def health(request):
    return JsonResponse({"status": "ok"})


def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def robots(request):
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


def page_context(user, workspace=None):
    workspaces = list(visible_workspaces(user).order_by("-is_personal", "name", "pk"))
    return {"workspace": workspace, "workspaces": workspaces, "personal": workspaces[0] if workspaces else None,
            "unread_alerts": visible_alerts(user, workspaces).filter(read_at=None).count() + visible_reminders(user, workspaces).filter(read_at=None).count()}


def visible_reminders(user, workspaces):
    return BillReminder.objects.filter(recipient=user, recurring__workspace__in=[w.pk for w in workspaces], recurring__status="confirmed")


def visible_alerts(user, workspaces):
    # An alert disappears with access: leaving a group hides its budgets' alerts.
    return BudgetAlert.objects.filter(recipient=user, silent=False, budget__workspace__in=[w.pk for w in workspaces])


@login_required
def alerts(request):
    for workspace in visible_workspaces(request.user):
        recurring.remind(workspace)  # bills due in the next three days, even before the daily task runs
    context = page_context(request.user)
    reminders = list(visible_reminders(request.user, context["workspaces"]).select_related("recurring__workspace").order_by("-due_on", "-pk")[:30])
    BillReminder.objects.filter(pk__in=[r.pk for r in reminders if r.read_at is None]).update(read_at=timezone.now())
    rows = list(visible_alerts(request.user, context["workspaces"]).select_related("budget__category", "budget__workspace").order_by("-created_at", "-pk")[:50])
    for alert in rows:
        # Amounts are recomputed from what this user can see now, never stored in the alert.
        alert.progress = budget_progress(request.user, alert.budget.workspace, [alert.budget], alert.period_start)[0]
    BudgetAlert.objects.filter(pk__in=[a.pk for a in rows if a.read_at is None]).update(read_at=timezone.now())
    return render(request, "budget/alerts.html", {**context, "alerts": rows, "reminders": reminders, "unread_alerts": 0})


def email_verified(user):
    return bool(user.email and user.verified_email == user.email.lower())


@login_required
def settings_page(request):
    return render(request, "budget/settings.html", {**page_context(request.user), "verified": email_verified(request.user),
                  "push_public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY if push.enabled() else "",
                  "mail_ready": "console" not in settings.EMAIL_BACKEND, "plaid": bank.enabled(),
                  "connections": request.user.bank_connections.annotate(account_count=Count("accounts")).order_by("institution_name", "pk")})


def plaid_connection(request, connection_id):
    if not bank.enabled():
        raise Http404
    return get_object_or_404(BankConnection, pk=connection_id, owner=request.user)


def sync_message(request, result, first=False):
    status, count = result
    if status == "busy":
        messages.info(request, "Synced less than a minute ago. Try again in a minute.")
    elif status == "error":
        messages.error(request, "The bank sync didn't finish. Nothing changed; try Sync now later.")
    elif first and not count:
        messages.info(request, "Plaid is still gathering your history. Try Sync now in a minute.")
    else:
        messages.success(request, f"Synced: {count} transaction{'' if count == 1 else 's'} added or updated.")


@login_required
def bank_connect(request):
    if not bank.enabled():
        raise Http404
    try:
        token = bank.link_token(request.user)
    except bank.PlaidError as error:
        token, failed = "", error.code
    else:
        failed = ""
    return render(request, "budget/bank_connect.html", {**page_context(request.user), "link_token": token, "failed": failed,
                                                        "exchange_url": reverse("bank_exchange"), "sandbox": settings.PLAID_ENV != "production"})


@login_required
@require_POST
def bank_exchange(request):
    if not bank.enabled():
        raise Http404
    body = _push_body(request)
    public_token, institution = body.get("public_token"), body.get("institution")
    if not (isinstance(public_token, str) and public_token.startswith("public-") and len(public_token) <= 200):
        return HttpResponse("Not a Plaid public token.", status=400, content_type="text/plain")
    try:
        access_token, item_id = bank.exchange(public_token)
    except bank.PlaidError:
        return HttpResponse("Plaid couldn't finish connecting. Try again.", status=502, content_type="text/plain")
    connection = BankConnection.objects.create(owner=request.user, item_id=item_id, access_token=bank.encrypt(access_token),
                                               institution_name=institution[:100] if isinstance(institution, str) else "")
    return JsonResponse({"next": reverse("bank_accounts", args=[connection.pk])})


@login_required
@require_http_methods(["GET", "POST"])
def bank_accounts(request, connection_id):
    """Choose which of the bank's accounts to import. Each one starts private; sharing stays a separate step."""
    connection = plaid_connection(request, connection_id)
    try:
        result = bank.accounts(connection)
    except bank.PlaidError:
        messages.error(request, "Plaid didn't return the accounts. Try again in a minute.")
        return redirect("settings")
    offered, institution = result["accounts"], result["institution_id"]
    if institution and connection.institution_id != institution:
        BankConnection.objects.filter(pk=connection.pk).update(institution_id=institution)
    imported = set(connection.accounts.values_list("provider_account_id", flat=True))
    if request.method == "POST":
        chosen = [a for a in offered if a["id"] in request.POST.getlist("accounts") and a["id"] not in imported]
        with transaction.atomic():
            for a in chosen:
                Account.objects.create(owner=request.user, name=(f"{a['name']} ••{a['mask']}" if a["mask"] else a["name"])[:80],
                                       connection=connection, provider_account_id=a["id"], mask=a["mask"], is_savings=a.get("subtype") in bank.SAVINGS_SUBTYPES)
            if chosen and connection.cursor:
                # The cursor already passed these accounts' history, so fetch it all again; known rows are updated, not duplicated.
                BankConnection.objects.filter(pk=connection.pk).update(cursor="", needs_sync=True)
        if chosen:
            sync_message(request, bank.sync(connection), first=True)
        return redirect("home")
    # The same bank connected twice (say, two logins that see one joint account): warn, and untick accounts that look the
    # same. Never merged automatically; matching last four digits is only a hint.
    twins = Account.objects.filter(owner=request.user, connection__institution_id=institution).exclude(connection=connection) if institution else Account.objects.none()
    twin_masks = set(twins.values_list("mask", flat=True)) - {""}
    for a in offered:
        a["imported"], a["duplicate"] = a["id"] in imported, a["mask"] in twin_masks
    return render(request, "budget/bank_accounts.html", {**page_context(request.user), "connection": connection, "offered": offered,
                                                         "connected_twice": twins.exists()})


@login_required
@require_POST
def bank_sync(request, connection_id):
    connection = plaid_connection(request, connection_id)
    sync_message(request, bank.sync(connection, manual=True))
    back = request.POST.get("next", "")
    return redirect(back if url_has_allowed_host_and_scheme(back, allowed_hosts=None) else "settings")


@login_required
def bank_reconnect(request, connection_id):
    """Update mode: the owner signs in to the bank again through Plaid; accounts and history stay as they are."""
    connection = plaid_connection(request, connection_id)
    try:
        token, failed = bank.link_token(request.user, connection), ""
    except bank.PlaidError as error:
        token, failed = "", error.code
    return render(request, "budget/bank_connect.html", {**page_context(request.user), "link_token": token, "failed": failed, "reconnect": connection,
                                                        "exchange_url": reverse("bank_reconnected", args=[connection.pk]),
                                                        "sandbox": settings.PLAID_ENV != "production"})


@login_required
@require_POST
def bank_reconnected(request, connection_id):
    # Update mode keeps the same access token, so there is nothing to exchange: clear the error and catch up.
    connection = plaid_connection(request, connection_id)
    BankConnection.objects.filter(pk=connection.pk).update(status="ok", error_code="")
    sync_message(request, bank.sync(connection))
    return JsonResponse({"next": reverse("settings")})


@csrf_exempt  # Plaid posts without a CSRF token or session; the signed JWT is the proof
@require_POST
def plaid_webhook(request):
    if not bank.enabled():
        raise Http404
    try:
        payload = bank.verify_webhook(request.body, request.headers.get("Plaid-Verification"))
    except bank.PlaidError:
        return HttpResponse(status=503)  # Plaid's signing key couldn't be fetched; Plaid retries
    if payload is None:
        return HttpResponse(status=400)
    bank.handle_webhook(payload)  # ponytail: syncs inside the request; move to a worker queue when there is one
    return HttpResponse(status=200)


@login_required
@require_POST
def bank_disconnect(request, connection_id):
    connection = plaid_connection(request, connection_id)
    try:
        bank.remove(connection)  # stop Plaid access; if Plaid can't be reached, the local disconnect still happens
    except bank.PlaidError:
        pass
    name = connection.institution_name or "the bank"
    connection.delete()  # accounts and history stay, as plain accounts
    messages.success(request, f"Disconnected {name}. Its accounts and history stay here; nothing syncs any more.")
    return redirect("settings")


@login_required
@require_POST
def email_alerts(request):
    on = request.POST.get("on") == "1"
    if on and not email_verified(request.user):
        messages.error(request, "Verify your email first, then turn on email alerts.")
    else:
        User.objects.filter(pk=request.user.pk).update(email_alerts=on)
        messages.success(request, "Email alerts are on." if on else "Email alerts are off.")
    return redirect("settings")


@login_required
@require_POST
def goals_toggle(request):
    on = request.POST.get("on") == "1"
    User.objects.filter(pk=request.user.pk).update(goals_enabled=on)
    messages.success(request, "Goals are on. Find them under Budgets." if on else "Goals are off. They're kept, just hidden.")
    return redirect("settings")


def goals_workspace(request, workspace_id):
    if not request.user.goals_enabled:
        raise Http404  # goals appear nowhere until this person turns them on
    return get_workspace(request.user, workspace_id)


@login_required
def goal_list(request, workspace_id):
    workspace = goals_workspace(request, workspace_id)
    today = timezone.localdate()
    return render(request, "budget/goals.html", {**page_context(request.user, workspace),
                  "goals": [goal_progress(g, request.user, today) for g in workspace.goals.select_related("account", "workspace").order_by("name", "pk")]})


@login_required
@require_http_methods(["GET", "POST"])
def goal_edit(request, workspace_id, goal_id=None):
    workspace = goals_workspace(request, workspace_id)
    goal = get_object_or_404(workspace.goals, pk=goal_id) if goal_id else Goal(workspace=workspace)
    form = GoalForm(request.POST if request.method == "POST" else None, instance=goal, accounts=visible_accounts(request.user, workspace))
    back = reverse("goals", args=[workspace.pk])
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Goal saved.")
        return redirect(back)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": f"Edit {goal.name}" if goal_id else "Add a goal",
                  "action": "Save goal", "cancel_url": back, "help": "A plan to track, not advice. Everyone in this workspace can see it.",
                  "delete_url": reverse("goal_delete", args=[workspace.pk, goal.pk]) if goal_id else None}, status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def goal_delete(request, workspace_id, goal_id):
    workspace = goals_workspace(request, workspace_id)
    get_object_or_404(workspace.goals, pk=goal_id).delete()
    messages.success(request, "Goal removed.")
    return redirect("goals", workspace.pk)


@csrf_exempt  # mail apps' one-click unsubscribe (RFC 8058) posts without a CSRF token; the signed link is the proof
@require_http_methods(["GET", "POST"])
def email_unsubscribe(request, token):
    """No sign-in needed. GET only asks, because link scanners open links; POST turns email alerts off."""
    try:
        user_id = int(signing.Signer(salt=UNSUBSCRIBE_SALT).unsign(token))
    except (signing.BadSignature, ValueError):
        raise Http404
    user = get_object_or_404(User, pk=user_id)
    if request.method == "POST":
        User.objects.filter(pk=user.pk).update(email_alerts=False)
    return render(request, "budget/email_unsubscribe.html", {"done": request.method == "POST"})


SERVICE_WORKER = """// Push only: no fetch handler, so no page or financial data is ever cached or intercepted.
self.addEventListener("push", (event) => {
  const d = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(d.title || "Budget", { body: d.body || "", tag: d.tag || "budget-alert", icon: "%s", data: { url: d.url || "/alerts/" } }));
});
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
"""


def service_worker(request):
    # Served from the site root so its scope covers the app; never cached so updates apply on the next visit.
    return HttpResponse(SERVICE_WORKER % static("budget/icons/icon-192.png"), content_type="application/javascript", headers={"Cache-Control": "no-cache"})


def _push_body(request):
    try:
        body = json.loads(request.body)
        return body if isinstance(body, dict) else {}
    except ValueError:
        return {}


@login_required
@require_POST
def push_subscribe(request):
    body = _push_body(request)
    endpoint, keys = body.get("endpoint"), body.get("keys") if isinstance(body.get("keys"), dict) else {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    fields_ok = all(isinstance(v, str) and 0 < len(v) <= limit for v, limit in ((endpoint, 500), (p256dh, 200), (auth, 100)))
    if not fields_ok or not push.valid_endpoint(endpoint):
        return HttpResponse("Not a supported push subscription.", status=400, content_type="text/plain")
    PushSubscription.objects.update_or_create(endpoint=endpoint, defaults={"user": request.user, "p256dh": p256dh, "auth": auth})
    return HttpResponse(status=204)


@login_required
@require_POST
def push_unsubscribe(request):
    endpoint = _push_body(request).get("endpoint")
    if isinstance(endpoint, str):
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    return HttpResponse(status=204)


def settings_form(request, form, status=200, **context):
    return render(request, "budget/form.html", {**page_context(request.user), "form": form, "cancel_url": reverse("settings"), **context}, status=status)


class PasswordChange(SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "budget/form.html"
    success_url = reverse_lazy("settings")
    success_message = "Password changed."
    extra_context = {"title": "Change password", "action": "Change password", "cancel_url": reverse_lazy("settings"),
                     "help": "Enter your current password, then a new one. You stay signed in on this device."}

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **page_context(self.request.user)}

    def form_valid(self, form):
        response = super().form_valid(form)
        notify(self.request, self.request.user, "Your Budget password was changed", "The password for your Budget login was just changed.")
        return response


@sensitive_post_parameters("current_password")
@login_required
@require_http_methods(["GET", "POST"])
def username_change(request):
    user = User.objects.get(pk=request.user.pk)  # a failed form must not rename request.user in the page header
    form = UsernameChangeForm(request.POST if request.method == "POST" else None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        notify(request, user, "Your Budget username was changed", f"Your Budget username is now {user.username}. Use it to sign in.")
        messages.success(request, "Username changed.")
        return redirect("settings")
    return settings_form(request, form, 400 if request.method == "POST" else 200, title="Change username", action="Change username",
                         help=f"You sign in as {request.user.username}. Enter the new username and your current password.")


EMAIL_CHANGE_SALT = "budget.email_change"
EMAIL_CHANGE_MAX_AGE = 3600


def password_stamp(user):
    # Any password change (including a reset) invalidates outstanding email-change links.
    return salted_hmac(EMAIL_CHANGE_SALT, user.password).hexdigest()[:16]


@sensitive_post_parameters("current_password")
@login_required
@require_http_methods(["GET", "POST"])
def email_change(request):
    user = request.user
    form = EmailChangeForm(request.POST if request.method == "POST" else None, user=user)
    if request.method == "POST" and form.is_valid():
        new = form.cleaned_data["email"]
        if not claim_email_send(user):
            form.add_error(None, "Please wait one minute before requesting another email.")
        else:
            token = signing.dumps({"u": user.pk, "e": new, "p": password_stamp(user)}, salt=EMAIL_CHANGE_SALT)
            link = request.build_absolute_uri(reverse("email_change_confirm", args=[token]))
            try:
                send_mail("Confirm your new Budget email", f"While signed in to Budget as {user.username}, open this link and confirm {new} as your email. It expires in one hour.\n\n{link}\n", None, [new])
            except (OSError, SMTPException):
                form.add_error(None, "The confirmation email could not be sent. Please try again in a minute.")
            else:
                notify(request, user, "A Budget email change was requested", f"Someone signed in as {user.username} asked to change the login email to {new}. Nothing changes unless that address confirms.")
                messages.success(request, f"Confirmation sent to {new}. Open its link while signed in. Your email stays the same until then.")
                return redirect("settings")
    return settings_form(request, form, 400 if request.method == "POST" else 200, title="Change email", action="Send confirmation",
                         help=f"Current email: {user.email or 'none'}. We send a link to the new address; the change happens when you open it.")


@login_required
@require_http_methods(["GET", "POST"])
def email_change_confirm(request, token):
    form = forms.Form(request.POST if request.method == "POST" else None)
    try:
        data = signing.loads(token, salt=EMAIL_CHANGE_SALT, max_age=EMAIL_CHANGE_MAX_AGE)
    except signing.BadSignature:
        data = None
    if data and data.get("u") != request.user.pk:
        raise Http404
    if request.method == "POST":
        user = request.user
        try:
            if not data or not constant_time_compare(data.get("p", ""), password_stamp(user)):
                raise ValidationError("This link is invalid or expired. Request a new one from Settings.")
            user.email = user.verified_email = data["e"]
            try:
                with transaction.atomic():
                    user.save(update_fields=["email", "verified_email"])
            except IntegrityError:
                raise ValidationError("Another login started using this email. Choose a different one.")
        except ValidationError as error:
            user.refresh_from_db()
            form.add_error(None, error)
        else:
            notify(request, user, "Your Budget email was changed", f"This is now the email for the Budget login {user.username}.")
            messages.success(request, "Email changed and verified.")
            return redirect("settings")
    return settings_form(request, form, 400 if request.method == "POST" else 200, title="Confirm new email", action="Confirm email",
                         help=f"Make {data['e'] if data else 'this address'} the email for {request.user.username}.")


@login_required
def home(request):
    workspace = get_object_or_404(visible_workspaces(request.user), is_personal=True)
    return redirect("workspace", workspace_id=workspace.pk)


def period(value, today):
    """'YYYY' is that year, 'YYYY-MM' that month, 'all' Lifetime (its dates come from period_context); anything else is
    this month. Returns (kind, start, end)."""
    if value == "all":
        return "all", None, None
    try:
        if len(value) == 4:
            return "year", date(int(value), 1, 1), date(int(value), 12, 31)
        start = date.fromisoformat(value + "-01")
    except ValueError:
        start = today.replace(day=1)
    return "month", start, (start + timedelta(days=32)).replace(day=1) - timedelta(days=1)


def labelled(rows, workspace):
    """Classification labels plus this workspace's split lines (row.splits, empty when not split)."""
    labels = dict(Transaction.CLASSIFICATIONS)
    lines = {}
    for line in SplitLine.objects.filter(workspace=workspace, transaction__in=[r.pk for r in rows]).select_related("category").order_by("pk"):
        lines.setdefault(line.transaction_id, []).append(line)
    for row in rows:
        row.effective_label = labels[row.effective]
        row.splits = lines.get(row.pk, [])
    return rows


def period_context(user, workspace, value):
    """The Overview and Savings page period: 1M, 1Y (with ← →) or Lifetime (first transaction to today, nothing to compare
    with). range_params is the same range for Timeline links."""
    today = timezone.localdate()
    kind, start, end = period(value, today)
    if kind == "all":
        start, end = first_day(user, workspace), today
        return {"kind": kind, "start": start, "end": end, "label": "Lifetime", "prev_range": None, "range_params": [("span", "all")],
                "periods": {"month": f"{today:%Y-%m}", "year": str(today.year)}}
    if kind == "year":
        label, prev, next_ = str(start.year), str(start.year - 1), str(start.year + 1)
    else:
        label, prev, next_ = date_format(start, "F Y"), f"{start - timedelta(days=1):%Y-%m}", f"{end + timedelta(days=1):%Y-%m}"
    _, prev_start, prev_end = period(prev, start)
    return {"kind": kind, "start": start, "end": end, "label": label, "prev": prev, "next": next_, "prev_range": (prev_start, prev_end),
            "prev_label": prev if kind == "year" else date_format(prev_start, "F"),
            "range_params": [("start", start.isoformat()), ("end", end.isoformat())],
            "periods": {"month": f"{start:%Y-%m}", "year": str(start.year)}}


@login_required
def workspace_detail(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    recurring.remind(workspace)
    context = page_context(request.user, workspace)
    context["memberships"] = Membership.objects.filter(workspace=workspace).select_related("user").exclude(user=workspace.owner)
    context.update(period_context(request.user, workspace, request.GET.get("period", "")))
    kind, start, end, prev_range = context["kind"], context["start"], context["end"], context["prev_range"]
    context["month"] = spending(request.user, workspace, start, end)
    context["series"] = daily(visible_transactions(request.user, workspace), start, end, by_month=kind != "month")
    context["table"] = {"year": context["series"], "all": by_year(context["series"])}.get(kind)
    context["range_query"] = urlencode(context["range_params"])
    context["change_cents"] = None if kind == "all" else context["month"]["posted_cents"] - spending(request.user, workspace, *prev_range)["posted_cents"]
    # One grouped query for each account's posted spending in the period (the row pill).
    per_account = {r["account"]: _shape(r)["posted_cents"] for r in visible_transactions(request.user, workspace)
                   .filter(posted_on__range=(start, end)).values("account").annotate(**_sums()).order_by()}
    context["accounts"] = list(visible_accounts(request.user, workspace).select_related("owner").order_by("name", "pk"))
    for account in context["accounts"]:
        account.period_cents = per_account.get(account.pk, 0)
    # Month view: monthly budgets for that month and yearly ones for their year. Year view: every budget over the year,
    # a monthly one at 12 times its limit. The total covers only budgets measured over the period shown.
    budgets = workspace.budgets.select_related("category").order_by("category__name", "name_match", "pk")
    # Lifetime has no budget period: the panel asks for 1M or 1Y instead.
    context["budgets"] = [] if kind == "all" else budget_progress(request.user, workspace, budgets, start, span=(start, end) if kind == "year" else None)
    same = [p for p in context["budgets"] if (p["start"], p["end"]) == (start, end)]
    context["budget_totals"] = {"limit_cents": sum(p["limit_cents"] for p in same), "spent_cents": sum(p["spent_cents"] for p in same),
                                "left_cents": sum(max(0, p["remaining_cents"]) for p in same), "over_cents": sum(max(0, -p["remaining_cents"]) for p in same)}
    context["categories"] = by_category(visible_transactions(request.user, workspace), start, end, workspace)
    top = max((c["posted_cents"] for c in context["categories"]), default=0)
    for c in context["categories"]:
        c["share"] = max(0, round(100 * c["posted_cents"] / top)) if top > 0 else 0
    context["membership_notices"] = MembershipNotice.objects.filter(workspace=workspace, recipient=request.user).order_by("-pk")[:20]
    context["worth"] = net_worth(request.user, workspace)
    saved = savings(request.user, workspace, start, end)
    saved.update(change_cents=None if kind == "all" else saved["net_cents"] - savings(request.user, workspace, *prev_range)["net_cents"],
                 timeline=savings_timeline(workspace, saved, context["range_params"]))
    context.update(saved=saved, savings_series=saved["days"] if kind == "month" else saved["months"])
    return render(request, "budget/workspace.html", context)


def savings_timeline(workspace, saved, range_params):
    """The Timeline's List view with the savings accounts ticked, where each transfer shows its line to checking."""
    return reverse("transactions", args=[workspace.pk]) + "?" + urlencode(
        [("view", "lanes"), *range_params, *(("account", a.pk) for a in saved["accounts"])])


@login_required
def savings_page(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    context = period_context(request.user, workspace, request.GET.get("period", ""))
    kind = context["kind"]
    saved = savings(request.user, workspace, context["start"], context["end"])
    return render(request, "budget/savings.html", {
        **page_context(request.user, workspace), **context, "saved": saved, "series": saved["days"] if kind == "month" else saved["months"],
        "timeline": savings_timeline(workspace, saved, context["range_params"]),
        "change_cents": None if kind == "all" else saved["net_cents"] - savings(request.user, workspace, *context["prev_range"])["net_cents"]})


@login_required
def net_worth_page(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    return render(request, "budget/net_worth.html", {**page_context(request.user, workspace), "worth": net_worth(request.user, workspace)})


@login_required
@require_http_methods(["GET", "POST"])
def account_edit(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    form = AccountForm(request.POST if request.method == "POST" else None, instance=account)
    back = reverse("account_detail", args=[workspace.pk, account.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            bump_account_data(account)
        messages.success(request, "Account saved.")
        return redirect(back)
    help = "Synced from your bank: its balance updates on every sync; choose whether it counts." if account.connection_id else "A manual account, or something you own or owe such as a home or a loan."
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": f"Edit {account.name}", "action": "Save account",
                  "cancel_url": back, "help": help}, status=400 if request.method == "POST" else 200)


@login_required
def account_detail(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(visible_accounts(request.user, workspace).select_related("connection"), pk=account_id)
    # ponytail: newest 100 only; the workspace timeline has the cursor-paged full history.
    transactions = labelled(list(annotated(account.transactions.order_by("-posted_on", "-pk"), workspace)[:100]), workspace)
    batches = account.imports.filter(status="done").order_by("-created_at")[:10] if account.owner_id == request.user.pk else []
    return render(request, "budget/account.html", {**page_context(request.user, workspace), "account": account, "transactions": transactions, "imports": batches})


@login_required
@require_http_methods(["GET", "POST"])
def account_import(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    posted = request.method == "POST"
    form = ImportUploadForm(request.POST if posted else None, request.FILES if posted else None, account=account)
    if posted and form.is_valid():
        # Unfinished previews hold a file's contents, so they don't linger.
        account.imports.filter(status="preview", created_at__lt=timezone.now() - timedelta(days=1)).delete()
        batch = account.imports.create(file_name=form.cleaned_data["file"].name[:200], sha256=form.sha256, content=form.text)
        return redirect("import_preview", workspace.pk, account.pk, batch.pk)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": f"Import a CSV into {account.name}",
                  "action": "Upload and preview", "cancel_url": reverse("account_detail", args=[workspace.pk, account.pk]),
                  "help": "Your bank's CSV export, one transaction per row. You pick the columns and check a preview before anything is saved."},
                  status=400 if posted else 200)


@login_required
@require_http_methods(["GET", "POST"])
def import_preview(request, workspace_id, account_id, batch_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    batch = get_object_or_404(account.imports, pk=batch_id)
    back = reverse("account_detail", args=[workspace.pk, account.pk])
    action = request.POST.get("action") if request.method == "POST" else None
    if batch.status == "done":
        messages.info(request, f"{batch.file_name} is already imported.")
        return redirect(back)
    if action == "cancel":
        batch.delete()
        return redirect(back)
    records = imports.rows(batch.content)
    header = imports.has_header(records[0])
    initial = {**imports.guess(records[0] if header else [], records[header:]), "header": header}
    form = ImportMappingForm(request.POST if action else None, initial=initial, records=records)
    mapping = initial if not form.is_bound else form.cleaned_data if form.is_valid() else None
    parsed, errors, skipped = imports.parse(records, mapping) if mapping else ([], [], 0)
    if action == "import" and mapping and not errors:
        result = imports.commit(batch, parsed, {int(k) for k in request.POST.getlist("keep") if k.isdigit()}, workspace)
        if result is None:
            messages.info(request, f"{batch.file_name} is already imported.")
        else:
            messages.success(request, f"Imported {result[0]} from {batch.file_name}." + (f" Skipped {result[1]} that look already imported." if result[1] else ""))
        return redirect(back)
    flagged = imports.overlaps(account, parsed)
    keep = set(request.POST.getlist("keep")) if action else set()
    categories = {c.name.casefold(): c.name for c in workspace.categories.filter(archived=False)}
    for p in parsed:
        p["flagged"], p["kept"] = p["source_row"] in flagged, str(p["source_row"]) in keep
        p["category_name"] = categories.get(p["category"].casefold(), "")
    return render(request, "budget/import_preview.html", {
        **page_context(request.user, workspace), "account": account, "batch": batch, "form": form, "errors": errors[:20],
        "more_errors": max(0, len(errors) - 20), "rows": parsed[:20], "more_rows": max(0, len(parsed) - 20),
        "flagged": [p for p in parsed if p["flagged"]], "skipped": skipped, "cancel_url": back,
        "count": sum(1 for p in parsed if not p["flagged"] or p["kept"]),
        "out_cents": sum(p["amount_cents"] for p in parsed if p["classification"] == "expense"),
        "in_cents": sum(p["amount_cents"] for p in parsed if p["classification"] != "expense"),
    }, status=400 if action == "import" else 200)


@login_required
@require_POST
def import_undo(request, workspace_id, account_id, batch_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    batch = get_object_or_404(account.imports, pk=batch_id, status="done")
    with transaction.atomic():
        batch.delete()  # its transactions, their notes and splits go with it
        bump_account_data(account)
    messages.success(request, f"Removed the {batch.row_count} transactions imported from {batch.file_name}.")
    return redirect("account_detail", workspace.pk, account.pk)


PAGE_SIZE = 50


def savings_mode(request):
    """The header's Spending | Savings switch, kept in a cookie so the server can render the Timeline for it."""
    return request.COOKIES.get("mode") == "savings"


def timeline_scope(request, workspace):
    """The Timeline's accounts and rows: everything visible, or in Savings mode only the savings accounts."""
    accounts, rows = visible_accounts(request.user, workspace), visible_transactions(request.user, workspace)
    if savings_mode(request):
        accounts = accounts.filter(is_savings=True)
        rows = rows.filter(account__in=accounts)
    return accounts, rows


@login_required
def transaction_list(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    accounts, visible = timeline_scope(request, workspace)
    saving = savings_mode(request)
    form = TransactionFilterForm(request.GET, accounts=accounts, workspace=workspace)
    context = {**page_context(request.user, workspace), "form": form, "rows": [], "next_query": None, "saving": saving,
               "no_savings": saving and not accounts.exists()}
    if not form.is_valid():
        return render(request, "budget/transactions.html", context, status=400)
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    filtered_rows = form.apply(visible)
    series = saved_daily if saving else daily
    by_month = (end - start).days > form.MAX_DAYS  # only Lifetime goes past two years; it charts by month
    days = series(filtered_rows, start, end, by_month=by_month)
    rows = filtered_rows.filter(posted_on__range=(start, end)).select_related("account__owner")
    # A cursor from before a data or sharing change could skip or repeat rows, so restart from newest.
    rev = f"{workspace.data_revision}-{workspace.permission_revision}"
    before = request.GET.get("before")
    stale = bool(before) and request.GET.get("rev") != rev
    if before and not stale:
        try:
            day, pk = before.split("_")
            day, pk = date.fromisoformat(day), int(pk)
        except ValueError:
            raise Http404
        rows = rows.filter(Q(posted_on__lt=day) | Q(posted_on=day, pk__lt=pk))
    # ponytail: keyset over all visible accounts; add a (posted_on, id) index if the load gate shows it matters.
    page = labelled(list(rows.order_by("-posted_on", "-pk")[:PAGE_SIZE + 1]), workspace)
    if len(page) > PAGE_SIZE:
        page, last = page[:PAGE_SIZE], page[PAGE_SIZE - 1]
        params = request.GET.copy()
        params["before"], params["rev"] = f"{last.posted_on:%Y-%m-%d}_{last.pk}", rev
        context["next_query"] = "?" + params.urlencode()
    heads = series(filtered_rows, page[-1].posted_on, page[0].posted_on) if by_month and page else days
    by_day = {d["day"]: d["posted_cents"] for d in heads}
    for row in page:
        row.day_posted = by_day[row.posted_on]
    newest = request.GET.copy()
    for key in ("before", "rev"):
        newest.pop(key, None)
    chosen = form.cleaned_data["category"]
    context["add_category"] = workspace.categories.filter(pk=int(chosen), archived=False).first() if chosen not in ("", "none") else None
    layouts = {}
    for name in ("together", "lanes"):
        query = newest.copy()
        query["view"] = name
        layouts[name] = "?" + query.urlencode()
    # 1M and 1Y are the calendar month and year of the range's end; the other filters stay.
    lifetime = form.cleaned_data["span"] == "all" and not request.GET.get("start") and not request.GET.get("end")
    ranges, today = [], timezone.localdate()
    for label, bounds in (("1M", period_bounds("month", end)), ("1Y", period_bounds("year", end)), ("Lifetime", None)):
        query = newest.copy()
        for key in ("start", "end", "span"):
            query.pop(key, None)
        if bounds:
            query["start"], query["end"] = bounds[0].isoformat(), bounds[1].isoformat()
        else:
            query["span"] = "all"
        current = lifetime if bounds is None else not lifetime and start == bounds[0] and end in (bounds[1], today)
        ranges.append((label, "?" + query.urlencode(), current))
    clear = QueryDict(mutable=True)
    for key in ("view", "start", "end", "span"):
        if request.GET.get(key):
            clear[key] = request.GET[key]
    context.update(rows=page, days=days, start=start, end=end, rev=rev, stale=stale, back=request.get_full_path(),
                   newest_query="?" + newest.urlencode(), paged=bool(before) and not stale, layouts=layouts, layout=form.cleaned_data["view"],
                   ranges=ranges, by_month=by_month, clear_query="?" + clear.urlencode() if clear else "",
                   totals={k: sum(d[k] for d in days) for k in (("in_cents", "out_cents", "posted_cents") if saving else ("posted_cents", "pending_cents", "income_cents"))},
                   filtered=any(request.GET.get(name) for name in form.fields if name not in ("view", "start", "end", "span")))
    if form.cleaned_data["view"] == "lanes":
        context.update(lane_context(request.user, workspace, form, filtered_rows, start, end))
    return render(request, "budget/transactions.html", context)


def lane_context(user, workspace, form, filtered_rows, start, end):
    """Side by side: one lane per ticked account (or per account with rows), newest day first, never a partial day."""
    rows = list(filtered_rows.filter(posted_on__range=(start, end)).select_related("account__owner").order_by("-posted_on", "-pk")[:flows.LANE_LIMIT + 1])
    capped = len(rows) > flows.LANE_LIMIT
    if capped:
        oldest = rows[flows.LANE_LIMIT - 1].posted_on
        rows = [r for r in rows[:flows.LANE_LIMIT] if r.posted_on != oldest] or rows[:flows.LANE_LIMIT]
    accounts = list(form.cleaned_data["account"]) or sorted({r.account for r in rows}, key=lambda a: (a.name, a.pk))
    # Partners may sit a few days outside the range; only visible transfers are candidates.
    oldest = rows[-1].posted_on if rows else start  # not the range start, so Lifetime doesn't scan every transfer
    candidates = visible_transactions(user, workspace).filter(effective="transfer", posted_on__range=(oldest - flows.WINDOW, end + flows.WINDOW)).select_related("account")
    return {"lanes": accounts, "bands": flows.lanes(rows, accounts, candidates), "capped": capped}


def csv_cell(value):
    # Spreadsheets run cells that start like a formula; a leading quote keeps them text.
    value = str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@login_required
def transaction_export(request, workspace_id):
    """The Timeline's rows as CSV: same filters and range cap, no paging."""
    workspace = get_workspace(request.user, workspace_id)
    accounts, visible = timeline_scope(request, workspace)
    form = TransactionFilterForm(request.GET, accounts=accounts, workspace=workspace)
    if not form.is_valid():
        return HttpResponse(" ".join(e for errors in form.errors.values() for e in errors), status=400, content_type="text/plain")
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    rows = labelled(list(form.apply(visible).filter(posted_on__range=(start, end))
                         .select_related("account__owner").order_by("-posted_on", "-pk")), workspace)
    response = HttpResponse(content_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="budget-{start:%Y-%m-%d}-{end:%Y-%m-%d}.csv"', "Cache-Control": "no-store"})
    writer = csv.writer(response)
    writer.writerow(["Date", "Account", "Owner", "Name", "Original description", "Category", "Classification", "Status", "Amount (USD)", "Note"])
    for row in rows:
        category = ("Split: " + "; ".join(f"{line.category.name} {line.amount_cents // 100}.{line.amount_cents % 100:02d}" for line in row.splits)
                    if row.splits else row.ann_category or "")
        names = [row.account.name, row.account.owner.username, row.ann_name or row.description, row.description, category, row.effective_label]
        writer.writerow([f"{row.posted_on:%Y-%m-%d}", *map(csv_cell, names), "Pending" if row.pending else "Posted",
                         f"{row.amount_cents // 100}.{row.amount_cents % 100:02d}", csv_cell(row.ann_note or "")])
    return response


@login_required
@require_http_methods(["GET", "POST"])
def transaction_edit(request, workspace_id, account_id, transaction_id=None):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    row = get_object_or_404(Transaction, account=account, pk=transaction_id) if transaction_id else Transaction(account=account)
    form = TransactionForm(request.POST if request.method == "POST" else None, instance=row)
    if row.from_bank:  # the bank's date, amount and description stay as imported
        for name in ("posted_on", "amount", "description", "pending"):
            form.fields[name].disabled = True
    back = reverse("account_detail", args=[workspace.pk, account.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            categorize_everywhere([form.instance])
            bump_account_data(account)
            evaluate_account(account)
        messages.success(request, "Transaction saved.")
        return redirect(back)
    title = "Edit transaction" if transaction_id else f"Add a transaction to {account.name}"
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": title, "action": "Save transaction", "cancel_url": back, "help": "From your bank: the date, amount and description stay as the bank sent them. You can change the type." if row.from_bank else "Manual entry. Transfers and card payments never count as spending."}, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def annotation_edit(request, workspace_id, account_id, transaction_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    row = get_object_or_404(Transaction, account=account, pk=transaction_id)
    instance = TransactionAnnotation.objects.filter(transaction=row, workspace=workspace).first() or TransactionAnnotation(transaction=row, workspace=workspace)
    form = AnnotationForm(request.POST if request.method == "POST" else None, instance=instance, source=row, personal=workspace.is_personal)
    back = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts=None):
        back = reverse("account_detail", args=[workspace.pk, account.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            if "category" in form.changed_data:
                drop_rule_splits(workspace, [row.pk])
            if form.cleaned_data["also_similar"]:
                ensure_rule(workspace, form.cleaned_data["match_text"], form.cleaned_data["category"])
                categorize(Transaction.objects.filter(account__in=visible_accounts(request.user, workspace)).only("pk", "description", "amount_cents", "provider_category"), workspace)
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
            evaluate(workspace)
        similar = form.cleaned_data["also_similar"]
        messages.success(request, "Changes saved for this workspace only." + (
            f" Transactions containing “{form.cleaned_data['match_text']}” now go to {form.cleaned_data['category']}." if similar else ""))
        return redirect(back)
    where = "your personal view" if workspace.is_personal else workspace.name
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": row.description or "Transaction", "action": "Save changes", "cancel_url": back,
                  "help": f"{date_format(row.posted_on)} · {dollars(row.amount_cents)} original. Changes here apply to {where} only; the original entry stays as recorded.",
                  "extra_url": reverse("transaction_edit", args=[workspace.pk, account.pk, row.pk]), "extra_label": "Edit type" if row.from_bank else "Edit original entry",
                  "split_url": reverse("transaction_split", args=[workspace.pk, account.pk, row.pk]) + (f"?next={quote(back)}" if request.GET.get("next") else "")}, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def category_list(request, workspace_id):
    """Any member may add, rename or archive this workspace's categories; they are shared labels, not accounts."""
    workspace = get_workspace(request.user, workspace_id)
    form = CategoryForm(request.POST if request.method == "POST" else None, instance=Category(workspace=workspace))
    del form.fields["archived"]
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Added {form.instance.name}.")
        return redirect("categories", workspace_id=workspace.pk)
    return render(request, "budget/categories.html", {**page_context(request.user, workspace), "form": form,
                  "categories": workspace.categories.order_by("archived", "name")}, status=400 if request.method == "POST" else 200)


SEARCH_LIMIT = 100


@login_required
@require_http_methods(["GET", "POST"])
def category_add(request, workspace_id, category_id):
    """Search this workspace's transactions by keyword, tick the ones that belong, and optionally make the
    keyword a rule so future matches land here too. Any member may do it: it only writes this overlay."""
    workspace = get_workspace(request.user, workspace_id)
    category = get_object_or_404(workspace.categories, pk=category_id, archived=False)
    data = request.POST if request.method == "POST" else request.GET
    q = " ".join(data.get("q", "").split())[:100]
    probe = Rule(kind="contains", pattern=q)
    # Matches the original description, exactly as the rule will. ponytail: Python scan of visible rows, like rules.
    rows = visible_transactions(request.user, workspace).annotate(ann_source=F("ann__category_source")).order_by("-posted_on", "-pk")
    found = [row for row in rows if matches(probe, row.description)] if normalize(q) else []
    if request.method == "POST":
        chosen = set(request.POST.getlist("ids"))
        picked = [row for row in found if str(row.pk) in chosen]
        keyword = " ".join(request.POST.get("keyword", q).split())
        make_rule = request.POST.get("make_rule") == "on" and bool(normalize(keyword))
        with transaction.atomic():
            existing = {a.transaction_id: a for a in TransactionAnnotation.objects.filter(workspace=workspace, transaction__in=[r.pk for r in picked])}
            for row in picked:
                annotation = existing.get(row.pk) or TransactionAnnotation(transaction=row, workspace=workspace)
                annotation.category, annotation.category_source = category, "manual"
                annotation.save()
            drop_rule_splits(workspace, [r.pk for r in picked])
            if make_rule:
                ensure_rule(workspace, keyword, category)
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
            evaluate(workspace)
        messages.success(request, f"Added {len(picked)} to {category.name}." + (f" Future “{keyword}” purchases will go there too." if make_rule else ""))
        return redirect("category_edit", workspace_id=workspace.pk, category_id=category.pk)
    for row in found:
        row.locked = row.ann_source == "manual" and bool(row.ann_category) and row.ann_category != category.name
    return render(request, "budget/category_add.html", {**page_context(request.user, workspace), "category": category, "q": q,
                  "rows": found[:SEARCH_LIMIT], "match_count": len(found)})


@login_required
@require_http_methods(["GET", "POST"])
def category_edit(request, workspace_id, category_id):
    workspace = get_workspace(request.user, workspace_id)
    category = get_object_or_404(workspace.categories, pk=category_id)
    form = CategoryForm(request.POST if request.method == "POST" else None, instance=category)
    back = reverse("categories", args=[workspace.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            if category.archived:
                category.rules.update(enabled=False)
                category.split_rules.update(enabled=False)
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
        messages.success(request, "Category saved." + (" Its rules are now off." if category.archived else ""))
        return redirect(back)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": f"Edit {category.name}", "action": "Save category",
                  "cancel_url": back, "help": f"Renaming changes the label on every {workspace.name} transaction in this category.",
                  "extra_url": reverse("category_add", args=[workspace.pk, category.pk]), "extra_label": "Add transactions"}, status=400 if request.method == "POST" else 200)


@login_required
def budget_list(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    budgets = workspace.budgets.select_related("category").order_by("category__name", "name_match", "pk")
    today = timezone.localdate()
    return render(request, "budget/budgets.html", {**page_context(request.user, workspace),
                  "budgets": budget_progress(request.user, workspace, budgets, today), "plan": disposable(request.user, workspace, today),
                  "upcoming": recurring.forecast(workspace, today)["items"][:3],
                  "goals": [goal_progress(g, request.user, today) for g in workspace.goals.select_related("account", "workspace").order_by("name", "pk")[:3]]
                  if request.user.goals_enabled else None})


@login_required
@require_http_methods(["GET", "POST"])
def bills(request, workspace_id):
    """Any member manages the workspace's recurring bills and income, like budgets."""
    workspace = get_workspace(request.user, workspace_id)
    today = timezone.localdate()
    found = recurring.candidates(request.user, workspace, today)
    if request.method == "POST":
        # Only a series the server finds itself can be confirmed; posted amounts or dates are never trusted.
        chosen = next((c for c in found if c["pattern"] == request.POST.get("pattern")), None)
        if chosen and request.POST.get("action") in ("confirm", "dismiss"):
            confirm = request.POST["action"] == "confirm"
            Recurring.objects.create(workspace=workspace, name=chosen["name"][:100], pattern=chosen["pattern"], kind=chosen["kind"],
                                     amount_cents=chosen["amount_cents"], interval=chosen["interval"], anchor_on=chosen["anchor_on"],
                                     status="confirmed" if confirm else "dismissed")
            messages.success(request, f"{chosen['name']} added. Check its amount and due date." if confirm else f"{chosen['name']} won't be suggested again.")
        return redirect("bills", workspace.pk)
    return render(request, "budget/bills.html", {**page_context(request.user, workspace), "forecast": recurring.forecast(workspace, today),
                  "items": workspace.recurring.filter(status="confirmed").order_by("kind", "name"), "found": found})


@login_required
@require_http_methods(["GET", "POST"])
def bill_edit(request, workspace_id, recurring_id=None):
    workspace = get_workspace(request.user, workspace_id)
    item = get_object_or_404(workspace.recurring, pk=recurring_id, status="confirmed") if recurring_id else Recurring(anchor_on=timezone.localdate())
    form = RecurringForm(request.POST if request.method == "POST" else None, instance=item, workspace=workspace)
    back = reverse("bills", args=[workspace.pk])
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Saved.")
        return redirect(back)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form,
                  "title": f"Edit {item.name}" if recurring_id else "Add a bill or income", "action": "Save", "cancel_url": back,
                  "help": "An estimate for planning. It never counts as spending; the real payment does when it posts.",
                  "delete_url": reverse("bill_delete", args=[workspace.pk, item.pk]) if recurring_id else None},
                  status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def bill_delete(request, workspace_id, recurring_id):
    workspace = get_workspace(request.user, workspace_id)
    get_object_or_404(workspace.recurring, pk=recurring_id).delete()
    messages.success(request, "Removed.")
    return redirect("bills", workspace.pk)


@csrf_exempt  # called by the scheduled GitHub Action with a bearer token, not a browser session
@require_POST
def daily_tasks(request):
    """Bill reminders for every workspace, and a catch-up bank sync for connections quiet for six hours."""
    if not settings.TASKS_TOKEN or not constant_time_compare(request.headers.get("Authorization", ""), f"Bearer {settings.TASKS_TOKEN}"):
        raise Http404
    today = timezone.localdate()
    for workspace in Workspace.objects.filter(recurring__status="confirmed", recurring__kind="bill", recurring__remind=True).distinct():
        recurring.remind(workspace, today)
    synced = 0
    if bank.enabled():
        quiet = Q(last_synced_at=None) | Q(last_synced_at__lt=timezone.now() - timedelta(hours=6))
        for connection in BankConnection.objects.filter(quiet, status="ok").order_by("pk"):
            bank.sync(connection)
            synced += 1
    return JsonResponse({"ok": True, "synced": synced})


@login_required
@require_http_methods(["GET", "POST"])
def income_edit(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    initial = {"income": Decimal(workspace.expected_income_cents) / 100} if workspace.expected_income_cents is not None else {}
    form = IncomeForm(request.POST if request.method == "POST" else None, initial=initial)
    back = reverse("budgets", args=[workspace.pk])
    if request.method == "POST" and form.is_valid():
        income = form.cleaned_data["income"]
        Workspace.objects.filter(pk=workspace.pk).update(expected_income_cents=None if income is None else int(income * 100))
        messages.success(request, "Income saved." if income is not None else "Using your recent average income.")
        return redirect(back)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "cancel_url": back,
                  "title": "Monthly income", "action": "Save income", "help": "Used only for the disposable income estimate on Budgets."},
                  status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def budget_edit(request, workspace_id, budget_id=None):
    """Any member may manage budgets; they only read spending this workspace can already see."""
    workspace = get_workspace(request.user, workspace_id)
    budget = get_object_or_404(workspace.budgets, pk=budget_id) if budget_id else Budget(workspace=workspace)
    form = BudgetForm(request.POST if request.method == "POST" else None, instance=budget)
    back = reverse("budgets", args=[workspace.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            # Already over when set or edited: a silent baseline, so the first alert is a real crossing.
            evaluate(workspace, silent=True, budgets=[form.instance])
        messages.success(request, "Budget saved.")
        return redirect(back)
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "cancel_url": back,
                  "title": "Edit budget" if budget.pk else "Add a budget", "action": "Save budget",
                  "help": "Posted spending counts; pending shows separately. Refunds reduce it and transfers never count. Nothing rolls over.",
                  "delete_url": reverse("budget_delete", args=[workspace.pk, budget.pk]) if budget.pk else None},
                  status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def budget_delete(request, workspace_id, budget_id):
    workspace = get_workspace(request.user, workspace_id)
    get_object_or_404(workspace.budgets, pk=budget_id).delete()
    messages.success(request, "Budget deleted.")
    return redirect("budgets", workspace_id=workspace.pk)


@login_required
def rule_list(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    return render(request, "budget/rules.html", {**page_context(request.user, workspace),
                  "rules": workspace.rules.select_related("category", "split_category").order_by("priority", "pk")})


PREVIEW_SIZE = 20


@login_required
@require_http_methods(["GET", "POST"])
def rule_edit(request, workspace_id, rule_id=None):
    """Any member may manage rules: they only change this workspace's overlay, never the original entries."""
    workspace = get_workspace(request.user, workspace_id)
    rule = get_object_or_404(workspace.rules, pk=rule_id) if rule_id else Rule(workspace=workspace)
    form = RuleForm(request.POST if request.method == "POST" else None, instance=rule)
    back = reverse("rules", args=[workspace.pk])
    context = {**page_context(request.user, workspace), "form": form, "cancel_url": back, "rule": rule}
    if request.method == "POST" and form.is_valid():
        # ponytail: matches in Python over every visible row (casefold has no SQL equivalent); batch it if history grows large.
        history = Transaction.objects.filter(account__in=visible_accounts(request.user, workspace)).order_by("-posted_on", "-pk")
        if "preview" in request.POST:
            found = [row for row in history.only("pk", "posted_on", "description", "amount_cents") if matches(form.instance, row.description)]
            return render(request, "budget/rule_form.html", {**context, "preview": found[:PREVIEW_SIZE], "match_count": len(found)})
        with transaction.atomic():
            form.save()
            changed = categorize(history.only("pk", "description", "amount_cents", "provider_category"), workspace) if form.cleaned_data["apply_existing"] else 0
            evaluate(workspace)
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
        messages.success(request, "Rule saved." + (f" {changed} existing transaction{'s' if changed != 1 else ''} updated." if form.cleaned_data["apply_existing"] else ""))
        return redirect(back)
    return render(request, "budget/rule_form.html", context, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def transaction_split(request, workspace_id, account_id, transaction_id):
    """Split one transaction across categories in this workspace only; the original entry never changes."""
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(editable_accounts(request.user, workspace), pk=account_id)
    row = get_object_or_404(Transaction, account=account, pk=transaction_id)
    existing = list(SplitLine.objects.filter(transaction=row, workspace=workspace).order_by("pk"))
    back = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(back, allowed_hosts=None):
        back = reverse("account_detail", args=[workspace.pk, account.pk])
    form = SplitForm(request.POST if request.method == "POST" and "remove" not in request.POST else None,
                     workspace=workspace, source=row, existing=existing)
    if request.method == "POST" and ("remove" in request.POST or form.is_valid()):
        with transaction.atomic():
            SplitLine.objects.filter(transaction=row, workspace=workspace).delete()
            if "remove" not in request.POST:
                SplitLine.objects.bulk_create(SplitLine(transaction=row, workspace=workspace, category=c, amount_cents=cents)
                                              for c, cents in form.cleaned_data["lines"])
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
            evaluate(workspace)
        messages.success(request, "Split removed." if "remove" in request.POST else "Split saved for this workspace only.")
        return redirect(back)
    return render(request, "budget/split.html", {**page_context(request.user, workspace), "form": form, "row": row, "existing": existing,
                  "cancel_url": back}, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def account_create(request):
    kind = request.GET.get("kind")
    form = AccountForm(request.POST if request.method == "POST" else None, initial={"balance_kind": kind} if kind in ("asset", "liability") else None)
    if request.method == "POST" and form.is_valid():
        account = form.save(commit=False)
        account.owner = request.user
        with transaction.atomic():
            account.save()
            bump_account_data(account)
        messages.success(request, "Account created. It is private until you choose to share it.")
        return redirect("home")
    return render(request, "budget/form.html", {**page_context(request.user), "form": form, "title": "Add a manual account", "action": "Create private account", "help": "Use a label, not an account number. For something you own or owe, like a home or a loan, add its current value."}, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def group_create(request):
    form = GroupForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        workspace = form.save(commit=False)
        workspace.owner = request.user
        workspace.save()
        messages.success(request, "Group created. No accounts are shared automatically.")
        return redirect("workspace", workspace_id=workspace.pk)
    return render(request, "budget/form.html", {**page_context(request.user), "form": form, "title": "Create a group", "action": "Create group", "help": "Keep a separate group for each set of people you want to share with. Invite people after creating the group."}, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def sharing(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    if workspace.is_personal:
        raise Http404
    form = SharingForm(request.POST if request.method == "POST" else None, user=request.user, workspace=workspace)
    if request.method == "POST" and form.is_valid():
        replace_shares(request.user, workspace.pk, [account.pk for account in form.cleaned_data["accounts"]])
        messages.success(request, "Sharing saved.")
        return redirect("workspace", workspace_id=workspace.pk)
    context = {**page_context(request.user, workspace), "form": form}
    context["memberships"] = Membership.objects.filter(workspace=workspace).select_related("user").exclude(user=workspace.owner)
    return render(request, "budget/sharing.html", context, status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def member_remove(request, workspace_id, member_id):
    try:
        remove_member(request.user, workspace_id, member_id)
    except ValidationError as error:
        return render(request, "budget/error.html", {**page_context(request.user), "error": error.messages[0]}, status=400)
    messages.success(request, "Membership and that person's account shares removed.")
    return redirect("home" if member_id == request.user.pk else "workspace", **({} if member_id == request.user.pk else {"workspace_id": workspace_id}))
