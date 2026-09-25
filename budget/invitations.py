import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import Invitation, Membership, MembershipNotice, User, Workspace
from .permissions import get_workspace
from .sharing import bump_permissions


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "budget.email_verification"

    def _make_hash_value(self, user, timestamp):
        return f"{user.pk}:{user.password}:{user.email}:{user.verified_email}:{timestamp}"


email_verification_token = EmailVerificationTokenGenerator()


def claim_email_send(user):
    now = timezone.now()
    return User.objects.filter(pk=user.pk, email=user.email).filter(
        Q(email_last_sent_at__isnull=True) | Q(email_last_sent_at__lte=now - timedelta(minutes=1))
    ).update(email_last_sent_at=now)


def get_invitation(token):
    return get_object_or_404(
        Invitation.objects.select_related("workspace__owner"),
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        accepted_at__isnull=True, revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )


def owned_workspace(user, workspace_id, *, lock=False):
    """A group or personal workspace the user owns; invitations on a personal one only create a login."""
    workspace = get_workspace(user, workspace_id, lock=lock)
    if workspace.owner_id != user.pk:
        raise Http404
    return workspace


@transaction.atomic
def create_signup_token(token):
    invitation = get_invitation(token)
    Workspace.objects.select_for_update().get(pk=invitation.workspace_id)
    invitation = get_invitation(token)
    if User.objects.filter(email__iexact=invitation.email).exists():
        raise ValidationError("An account already uses this email. Sign in or recover that account.")
    now = timezone.now()
    if invitation.signup_sent_at and invitation.signup_sent_at > now - timedelta(minutes=1):
        raise ValidationError("Please wait one minute before requesting another setup email.")
    proof = secrets.token_urlsafe(32)
    invitation.signup_token_hash = hashlib.sha256(proof.encode()).hexdigest()
    invitation.signup_sent_at = now
    invitation.save(update_fields=["signup_token_hash", "signup_sent_at"])
    return invitation, proof


def get_signup_invitation(token, proof):
    invitation = get_invitation(token)
    if (not invitation.signup_sent_at
        or invitation.signup_sent_at <= timezone.now() - timedelta(hours=1)
        or not constant_time_compare(invitation.signup_token_hash, hashlib.sha256(proof.encode()).hexdigest())):
        raise Http404
    return invitation


@transaction.atomic
def create_invitation(user, workspace_id, email):
    workspace = owned_workspace(user, workspace_id, lock=True)
    email = email.strip().lower()
    Invitation._meta.get_field("email").clean(email, None)
    now = timezone.now()
    recent = workspace.invitations.filter(created_at__gt=now - timedelta(hours=1))
    if recent.count() >= 20 or recent.filter(email=email, created_at__gt=now - timedelta(minutes=1)).exists():
        raise ValidationError("Please wait before sending another invitation.")
    workspace.invitations.filter(email=email, accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=now)
    token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        workspace=workspace, email=email,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=now + timedelta(days=7),
    )
    return invitation, token


@transaction.atomic
def revoke_invitation(user, workspace_id, invitation_id):
    workspace = owned_workspace(user, workspace_id, lock=True)
    invitation = get_object_or_404(Invitation, workspace=workspace, pk=invitation_id)
    if invitation.accepted_at is None:
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["revoked_at"])


@transaction.atomic
def accept_invitation(user, token):
    invitation = get_invitation(token)
    # Same lock order as sharing/removal; re-read the token after the lock.
    Workspace.objects.select_for_update().get(pk=invitation.workspace_id)
    invitation = get_invitation(token)
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or not user.email or user.email.lower() != invitation.email:
        raise ValidationError("Sign in with the account for the invited email address.")
    if user.verified_email != user.email.lower():
        raise ValidationError("Verify your email address before joining this group.")
    workspace = invitation.workspace
    if user.pk != workspace.owner_id and not workspace.is_personal:
        _, created = Membership.objects.get_or_create(workspace=workspace, user=user)
        if created:
            recipients = set(workspace.account_shares.values_list("account__owner_id", flat=True))
            recipients.add(workspace.owner_id)
            MembershipNotice.objects.bulk_create([
                MembershipNotice(workspace=workspace, recipient_id=recipient, member_name=user.username)
                for recipient in recipients - {user.pk}
            ])
            bump_permissions(workspace)
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    return workspace


@transaction.atomic
def verify_email(user, token):
    user = User.objects.select_for_update().get(pk=user.pk)
    if not user.is_active or not user.email or not email_verification_token.check_token(user, token):
        raise ValidationError("This verification link is invalid or expired. Request a new one.")
    user.verified_email = user.email.lower()
    user.save(update_fields=["verified_email"])
