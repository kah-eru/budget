from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AccountForm, AnnotationForm, GroupForm, SharingForm, TransactionFilterForm, TransactionForm
from .models import Membership, MembershipNotice, Transaction, TransactionAnnotation, Workspace
from .permissions import editable_accounts, get_workspace, visible_accounts, visible_workspaces
from .reporting import annotated, monthly, spending, visible_transactions
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
    return {"workspace": workspace, "workspaces": visible_workspaces(user).order_by("-is_personal", "name", "pk")}


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


def labelled(rows):
    labels = dict(Transaction.CLASSIFICATIONS)
    for row in rows:
        row.effective_label = labels[row.effective]
    return rows


@login_required
def workspace_detail(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    context = page_context(request.user, workspace)
    context["accounts"] = visible_accounts(request.user, workspace).select_related("owner").order_by("name", "pk")
    context["memberships"] = Membership.objects.filter(workspace=workspace).select_related("user").exclude(user=workspace.owner)
    kind, start, end = period(request.GET.get("period", ""), timezone.localdate())
    context.update(kind=kind, start=start, end=end, month=spending(request.user, workspace, start, end))
    if kind == "year":
        context.update(label=str(start.year), prev=str(start.year - 1), next=str(start.year + 1), months=monthly(request.user, workspace, start.year))
    else:
        context.update(label=date_format(start, "F Y"), prev=f"{start - timedelta(days=1):%Y-%m}", next=f"{end + timedelta(days=1):%Y-%m}")
    context["membership_notices"] = MembershipNotice.objects.filter(workspace=workspace, recipient=request.user).order_by("-pk")[:20]
    return render(request, "budget/workspace.html", context)


@login_required
def account_detail(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(visible_accounts(request.user, workspace), pk=account_id)
    # ponytail: newest 100 only; the timeline slice adds (date, id) cursor paging.
    transactions = labelled(list(annotated(account.transactions.order_by("-posted_on", "-pk"), workspace)[:100]))
    return render(request, "budget/account.html", {**page_context(request.user, workspace), "account": account, "transactions": transactions})


PAGE_SIZE = 50


@login_required
def transaction_list(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    form = TransactionFilterForm(request.GET, accounts=visible_accounts(request.user, workspace))
    context = {**page_context(request.user, workspace), "form": form, "rows": [], "next_query": None}
    if not form.is_valid():
        return render(request, "budget/transactions.html", context, status=400)
    rows = form.apply(visible_transactions(request.user, workspace)).select_related("account__owner")
    if before := request.GET.get("before"):
        try:
            day, pk = before.split("_")
            day, pk = date.fromisoformat(day), int(pk)
        except ValueError:
            raise Http404
        rows = rows.filter(Q(posted_on__lt=day) | Q(posted_on=day, pk__lt=pk))
    # ponytail: keyset over all visible accounts; add a (posted_on, id) index if the load gate shows it matters.
    page = labelled(list(rows.order_by("-posted_on", "-pk")[:PAGE_SIZE + 1]))
    if len(page) > PAGE_SIZE:
        page, last = page[:PAGE_SIZE], page[PAGE_SIZE - 1]
        params = request.GET.copy()
        params["before"] = f"{last.posted_on:%Y-%m-%d}_{last.pk}"
        context["next_query"] = "?" + params.urlencode()
    context.update(rows=page, back=request.get_full_path(), filtered=any(form.cleaned_data.values()) or bool(before))
    return render(request, "budget/transactions.html", context)


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
            bump_account_data(account)
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
            Workspace.objects.filter(pk=workspace.pk).update(data_revision=F("data_revision") + 1)
        messages.success(request, "Changes saved for this workspace only.")
        return redirect(back)
    where = "your personal view" if workspace.is_personal else workspace.name
    return render(request, "budget/form.html", {**page_context(request.user, workspace), "form": form, "title": row.description or "Transaction", "action": "Save changes", "cancel_url": back,
                  "help": f"{date_format(row.posted_on)} · {dollars(row.amount_cents)} original. Changes here apply to {where} only; the original entry stays as recorded.",
                  "extra_url": reverse("transaction_edit", args=[workspace.pk, account.pk, row.pk]), "extra_label": "Edit original entry"}, status=400 if request.method == "POST" else 200)


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
