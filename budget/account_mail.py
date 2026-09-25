from smtplib import SMTPException

from django.core.mail import send_mail
from django.urls import reverse


def notify(request, user, subject, what):
    """Tell the verified address about a completed change. Mail failure never undoes the change."""
    if not user.verified_email:
        return
    reset = request.build_absolute_uri(reverse("password_reset"))
    try:
        send_mail(subject, f"{what}\n\nIf this wasn't you, reset your password now: {reset}\n", None, [user.verified_email])
    except (OSError, SMTPException):
        pass
