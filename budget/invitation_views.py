from smtplib import SMTPException

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AcceptInvitationForm, InvitationForm, InvitedUserForm
from .invitations import (
    accept_invitation, claim_email_send, create_invitation, email_verification_token,
    create_signup_token, get_invitation, get_signup_invitation, owned_workspace, revoke_invitation, verify_email,
)
from .models import Invitation, User, Workspace
from .views import page_context


@login_required
@require_http_methods(["GET", "POST"])
def invitation_create(request, workspace_id):
    workspace = owned_workspace(request.user, workspace_id)
    form = InvitationForm(request.POST if request.method == "POST" else None, personal=workspace.is_personal)
    if request.method == "POST" and form.is_valid():
        try:
            invitation, token = create_invitation(request.user, workspace.pk, form.cleaned_data["email"])
            link = request.build_absolute_uri(reverse("invitation_accept", args=[token]))
            try:
                if workspace.is_personal:
                    send_mail("Your Budget invitation", f"You are invited to Budget. Open this link to create your own private login. The invitation expires in seven days.\n\n{link}\n", None, [invitation.email])
                else:
                    send_mail("Budget group invitation", f"You are invited to a Budget group. Sign in or create an account, verify your email, then choose whether to join. The invitation expires in seven days.\n\n{link}\n", None, [invitation.email])
            except (OSError, SMTPException):
                Invitation.objects.filter(pk=invitation.pk).update(revoked_at=timezone.now())
                raise ValidationError("The invitation could not be sent. Please try again in a minute.")
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, "Invitation sent." if workspace.is_personal else "Invitation sent. The recipient must verify their email before joining.")
            return redirect("invitation_create", workspace_id=workspace.pk)
    pending = workspace.invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).order_by("-pk")
    return render(request, "budget/invitations.html", {
        **page_context(request.user, workspace), "form": form,
        "invitations": Paginator(pending, 20).get_page(request.GET.get("page")),
    }, status=400 if request.method == "POST" else 200)


@login_required
@require_POST
def invitation_revoke(request, workspace_id, invitation_id):
    revoke_invitation(request.user, workspace_id, invitation_id)
    messages.success(request, "Invitation revoked.")
    return redirect("invitation_create", workspace_id=workspace_id)


@require_http_methods(["GET", "POST"])
def invitation_accept(request, token):
    invitation = get_invitation(token)
    form = AcceptInvitationForm(request.POST if request.method == "POST" else None, personal=invitation.workspace.is_personal)
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"{reverse('login')}?next={request.path}")
        if form.is_valid():
            try:
                workspace = accept_invitation(request.user, token)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                if workspace.is_personal:
                    messages.success(request, "Your login is ready.")
                    return redirect("home")
                messages.success(request, "You joined the group. Your own accounts are still private.")
                return redirect("workspace", workspace_id=workspace.pk)
    return render(request, "budget/invitation_accept.html", {"invitation": invitation, "form": form, "token": token}, status=400 if request.method == "POST" else 200)


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def invitation_register(request, token, proof=None):
    invitation = get_signup_invitation(token, proof) if proof else get_invitation(token)
    if request.user.is_authenticated:
        return redirect("invitation_accept", token=token)
    if not proof:
        form = forms.Form(request.POST if request.method == "POST" else None)
        if request.method == "POST":
            try:
                invitation, setup_token = create_signup_token(token)
                link = request.build_absolute_uri(reverse("invitation_register_confirm", args=[token, setup_token]))
                send_mail("Set up your Budget account", f"Open this separate email link to choose your username and password. It expires in one hour.\n\n{link}\n", None, [invitation.email])
            except (OSError, SMTPException):
                form.add_error(None, "The setup email could not be sent. Please try again in a minute.")
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Check your email for the account setup link.")
                return redirect("invitation_register", token=token)
        return render(request, "budget/form.html", {
            "form": form, "title": "Verify your email to create an account", "action": "Send account setup email",
            "help": "We will send a separate setup link to the invited email address. Open it to choose your username and password.",
            "cancel_url": reverse("invitation_accept", args=[token]),
        }, status=400 if request.method == "POST" else 200)
    form = InvitedUserForm(request.POST if request.method == "POST" else None, instance=User(email=invitation.email))
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                Workspace.objects.select_for_update().get(pk=invitation.workspace_id)
                invitation = get_signup_invitation(token, proof)
                if User.objects.filter(email__iexact=invitation.email).exists():
                    raise ValidationError("An account already uses this email. Sign in or recover that account.")
                form.instance.verified_email = invitation.email
                form.save()
                invitation.signup_token_hash = ""
                invitation.save(update_fields=["signup_token_hash"])
        except (ValidationError, IntegrityError):
            form.add_error(None, "This account could not be created. If you already have an account, sign in or recover it.")
        else:
            messages.success(request, "Account created and email verified. Sign in to choose whether to join the group.")
            return redirect(f"{reverse('login')}?next={reverse('invitation_accept', args=[token])}")
    return render(request, "budget/form.html", {
        "form": form, "title": "Create your invited account", "action": "Create account",
        "help": "Your email has been verified by this setup link. Creating an account does not join the group; you will choose after signing in.",
        "cancel_url": reverse("invitation_accept", args=[token]),
    }, status=400 if request.method == "POST" else 200)


@login_required
@require_http_methods(["GET", "POST"])
def email_verify(request, token=None):
    form = forms.Form(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        try:
            if token:
                verify_email(request.user, token)
                messages.success(request, "Email verified. Return to your invitation to join the group.")
            else:
                if not request.user.email:
                    raise ValidationError("Your account has no email address. Ask the operator to set it before verification.")
                if request.user.verified_email == request.user.email.lower():
                    raise ValidationError("Your current email is already verified.")
                if not claim_email_send(request.user):
                    raise ValidationError("Please wait one minute before requesting another email.")
                link = request.build_absolute_uri(reverse("email_verify_confirm", args=[email_verification_token.make_token(request.user)]))
                send_mail("Verify your Budget email", f"While signed in to your Budget account, open this link and confirm your email. It expires in one hour.\n\n{link}\n", None, [request.user.email])
                messages.success(request, "Verification email sent. Open its link while signed in, then return to your invitation.")
        except (OSError, SMTPException):
            form.add_error(None, "The verification email could not be sent. Please try again in a minute.")
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect("email_verify")
    verified = bool(request.user.email and request.user.verified_email == request.user.email.lower())
    return render(request, "budget/form.html", {
        **page_context(request.user), "form": form,
        "title": "Verify your email", "action": "Confirm email" if token else "Send verification email",
        "help": f"{request.user.email or 'No email set'}. " + ("Your current email is verified." if verified else "Email verification is required to join a group and recover your password."),
        "hide_submit": verified and not token,
    }, status=400 if request.method == "POST" else 200)
