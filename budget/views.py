from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AccountForm, GroupForm, SharingForm, TransactionForm
from .models import Membership, MembershipNotice, Transaction
from .permissions import editable_accounts, get_workspace, visible_accounts, visible_workspaces
from .reporting import spending
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


@login_required
def workspace_detail(request, workspace_id):
    workspace = get_workspace(request.user, workspace_id)
    context = page_context(request.user, workspace)
    context["accounts"] = visible_accounts(request.user, workspace).select_related("owner").order_by("name", "pk")
    context["memberships"] = Membership.objects.filter(workspace=workspace).select_related("user").exclude(user=workspace.owner)
    today = timezone.localdate()
    context["month"] = spending(request.user, workspace, today.replace(day=1), today)
    context["membership_notices"] = MembershipNotice.objects.filter(workspace=workspace, recipient=request.user).order_by("-pk")[:20]
    return render(request, "budget/workspace.html", context)


@login_required
def account_detail(request, workspace_id, account_id):
    workspace = get_workspace(request.user, workspace_id)
    account = get_object_or_404(visible_accounts(request.user, workspace), pk=account_id)
    # ponytail: newest 100 only; the timeline slice adds (date, id) cursor paging.
    transactions = account.transactions.order_by("-posted_on", "-pk")[:100]
    return render(request, "budget/account.html", {**page_context(request.user, workspace), "account": account, "transactions": transactions})


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
