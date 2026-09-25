import csv
import json
from datetime import date, timedelta
from decimal import Decimal
from smtplib import SMTPException
from urllib.parse import quote

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
from django.db.models import F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .account_mail import notify
from .forms import (
    AccountForm, AnnotationForm, BudgetForm, CategoryForm, EmailChangeForm, GroupForm, IncomeForm, RuleForm, SplitForm, SharingForm, TransactionFilterForm, TransactionForm, UsernameChangeForm,
)
from .invitations import claim_email_send
from .models import Budget, BudgetAlert, Category, Membership, MembershipNotice, PushSubscription, Rule, SplitLine, Transaction, TransactionAnnotation, User, Workspace
from .permissions import editable_accounts, get_workspace, visible_accounts, visible_workspaces
from .reporting import _shape, _sums, annotated, budget_progress, by_category, disposable, daily, monthly, spending, visible_transactions
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
            "unread_alerts": visible_alerts(user, workspaces).filter(read_at=None).count()}


def visible_alerts(user, workspaces):
    # An alert disappears with access: leaving a group hides its budgets' alerts.
    return BudgetAlert.objects.filter(recipient=user, silent=False, budget__workspace__in=[w.pk for w in workspaces])


@login_required
def alerts(request):
    context = page_context(request.user)
    rows = list(visible_alerts(request.user, context["workspaces"]).select_related("budget__category", "budget__workspace").order_by("-created_at", "-pk")[:50])
    for alert in rows:
        # Amounts are recomputed from what this user can see now, never stored in the alert.
        alert.progress = budget_progress(request.user, alert.budget.workspace, [alert.budget], alert.period_start)[0]
    BudgetAlert.objects.filter(pk__in=[a.pk for a in rows if a.read_at is None]).update(read_at=timezone.now())
    return render(request, "budget/alerts.html", {**context, "alerts": rows, "unread_alerts": 0})


def email_verified(user):
    return bool(user.email and user.verified_email == user.email.lower())


@login_required
def settings_page(request):
    return render(request, "budget/settings.html", {**page_context(request.user), "verified": email_verified(request.user),
                  "push_public_key": settings.WEBPUSH_VAPID_PUBLIC_KEY if push.enabled() else ""})


SERVICE_WORKER = """// Push only: no fetch handler, so no page or financial data is ever cached or intercepted.
self.addEventListener("push", (event) => {
  const d = event.data ? event.data.json() : {};
  event.waitUntil(self.registration.showNotification(d.title || "Budget", { body: d.body || "", tag: "budget-alert", icon: "%s", data: { url: d.url || "/alerts/" } }));
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
    """'YYYY' is that year, 'YYYY-MM' that month; anything else is this month. Returns (kind, start, end)."""
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


@login_required
def workspace_detail(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    context = page_context(request.user, workspace)
    context["memberships"] = Membership.objects.filter(workspace=workspace).select_related("user").exclude(user=workspace.owner)
    kind, start, end = period(request.GET.get("period", ""), timezone.localdate())
    context.update(kind=kind, start=start, end=end, month=spending(request.user, workspace, start, end))
    if kind == "year":
        months, running = monthly(request.user, workspace, start.year), 0
        for m in months:
            running += m["posted_cents"]
            m.update(day=m["month"], cumulative_cents=running)
        context.update(label=str(start.year), prev=str(start.year - 1), next=str(start.year + 1), months=months, series=months)
        _, prev_start, prev_end = period(str(start.year - 1), start)
    else:
        context.update(label=date_format(start, "F Y"), prev=f"{start - timedelta(days=1):%Y-%m}", next=f"{end + timedelta(days=1):%Y-%m}",
                       series=daily(visible_transactions(request.user, workspace), start, end))
        _, prev_start, prev_end = period(f"{start - timedelta(days=1):%Y-%m}", start)
    context["prev_label"] = str(prev_start.year) if kind == "year" else date_format(prev_start, "F")
    context["change_cents"] = context["month"]["posted_cents"] - spending(request.user, workspace, prev_start, prev_end)["posted_cents"]
    # One grouped query for each account's posted spending in the period (the row pill).
    per_account = {r["account"]: _shape(r)["posted_cents"] for r in visible_transactions(request.user, workspace)
                   .filter(posted_on__range=(start, end)).values("account").annotate(**_sums()).order_by()}
    context["accounts"] = list(visible_accounts(request.user, workspace).select_related("owner").order_by("name", "pk"))
    for account in context["accounts"]:
        account.period_cents = per_account.get(account.pk, 0)
    # Month view: monthly budgets for that month and yearly ones for its year; year view: yearly budgets only.
    budgets = workspace.budgets.select_related("category").order_by("category__name", "name_match", "pk")
    context["budgets"] = budget_progress(request.user, workspace, budgets if kind == "month" else budgets.filter(period="year"), start)
    context["categories"] = by_category(visible_transactions(request.user, workspace), start, end, workspace)
    top = max((c["posted_cents"] for c in context["categories"]), default=0)
    for c in context["categories"]:
        c["share"] = max(0, round(100 * c["posted_cents"] / top)) if top > 0 else 0
    context["membership_notices"] = MembershipNotice.objects.filter(workspace=workspace, recipient=request.user).order_by("-pk")[:20]
    return render(request, "budget/workspace.html", context)


@login_required
def account_detail(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(visible_accounts(request.user, workspace), pk=account_id)
    # ponytail: newest 100 only; the workspace timeline has the cursor-paged full history.
    transactions = labelled(list(annotated(account.transactions.order_by("-posted_on", "-pk"), workspace)[:100]), workspace)
    return render(request, "budget/account.html", {**page_context(request.user, workspace), "account": account, "transactions": transactions})


PAGE_SIZE = 50


@login_required
def transaction_list(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    form = TransactionFilterForm(request.GET, accounts=visible_accounts(request.user, workspace), workspace=workspace)
    context = {**page_context(request.user, workspace), "form": form, "rows": [], "next_query": None}
    if not form.is_valid():
        return render(request, "budget/transactions.html", context, status=400)
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    filtered_rows = form.apply(visible_transactions(request.user, workspace))
    days = daily(filtered_rows, start, end)
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
    by_day = {d["day"]: d["posted_cents"] for d in days}
    for row in page:
        row.day_posted = by_day[row.posted_on]
    newest = request.GET.copy()
    for key in ("before", "rev"):
        newest.pop(key, None)
    chosen = form.cleaned_data["category"]
    context["add_category"] = workspace.categories.filter(pk=int(chosen), archived=False).first() if chosen not in ("", "none") else None
    context.update(rows=page, days=days, start=start, end=end, rev=rev, stale=stale, back=request.get_full_path(),
                   newest_query="?" + newest.urlencode(), paged=bool(before) and not stale,
                   totals={k: sum(d[k] for d in days) for k in ("posted_cents", "pending_cents", "income_cents")},
                   filtered=any(request.GET.get(name) for name in form.fields))
    return render(request, "budget/transactions.html", context)


def csv_cell(value):
    # Spreadsheets run cells that start like a formula; a leading quote keeps them text.
    value = str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@login_required
def transaction_export(request, workspace_id):
    """The Timeline's rows as CSV: same filters and range cap, no paging."""
    workspace = get_workspace(request.user, workspace_id)
    form = TransactionFilterForm(request.GET, accounts=visible_accounts(request.user, workspace), workspace=workspace)
    if not form.is_valid():
        return HttpResponse(" ".join(e for errors in form.errors.values() for e in errors), status=400, content_type="text/plain")
    start, end = form.cleaned_data["start"], form.cleaned_data["end"]
    rows = labelled(list(form.apply(visible_transactions(request.user, workspace)).filter(posted_on__range=(start, end))
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
    back = reverse("account_detail", args=[workspace.pk, account.pk])
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            categorize_everywhere(form.instance)
            bump_account_data(account)
            evaluate_account(account)
        messages.success(request, "Transaction saved.")
        return redirect(back)
    title = "Edit transaction" if transaction_id else f"Add a transaction to {account.name}"
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": title, "action": "Save transaction", "cancel_url": back, "help": "Manual entry. Transfers and card payments never count as spending."}, status=400 if request.method == "POST" else 200)


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
                categorize(Transaction.objects.filter(account__in=visible_accounts(request.user, workspace)).only("pk", "description", "amount_cents"), workspace)
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
            evaluate(workspace)
        similar = form.cleaned_data["also_similar"]
        messages.success(request, "Changes saved for this workspace only." + (
            f" Transactions containing “{form.cleaned_data['match_text']}” now go to {form.cleaned_data['category']}." if similar else ""))
        return redirect(back)
    where = "your personal view" if workspace.is_personal else workspace.name
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": row.description or "Transaction", "action": "Save changes", "cancel_url": back,
                  "help": f"{date_format(row.posted_on)} · {dollars(row.amount_cents)} original. Changes here apply to {where} only; the original entry stays as recorded.",
                  "extra_url": reverse("transaction_edit", args=[workspace.pk, account.pk, row.pk]), "extra_label": "Edit original entry",
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
                  "budgets": budget_progress(request.user, workspace, budgets, today), "plan": disposable(request.user, workspace, today)})


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
            changed = categorize(history.only("pk", "description", "amount_cents"), workspace) if form.cleaned_data["apply_existing"] else 0
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
    form = AccountForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        account = form.save(commit=False)
        account.owner = request.user
        with transaction.atomic():
            account.save()
            bump_account_data(account)
        messages.success(request, "Account created. It is private until you choose to share it.")
        return redirect("home")
    return render(request, "budget/form.html", {**page_context(request.user), "form": form, "title": "Add a manual account", "action": "Create private account", "help": "Use a label, not an account number. Bank connections and CSV imports are not available yet."}, status=400 if request.method == "POST" else 200)


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
