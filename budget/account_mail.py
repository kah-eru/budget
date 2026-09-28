import logging
from smtplib import SMTPException

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMessage, get_connection, send_mail
from django.urls import reverse

from .models import User

log = logging.getLogger(__name__)
UNSUBSCRIBE_SALT = "budget.email-alerts.unsubscribe"


def notify(request, user, subject, what):
    """Tell the verified address about a completed change. Mail failure never undoes the change."""
    if not user.verified_email:
        return
    reset = request.build_absolute_uri(reverse("password_reset"))
    try:
        send_mail(subject, f"{what}\n\nIf this wasn't you, reset your password now: {reset}\n", None, [user.verified_email])
    except (OSError, SMTPException):
        pass


def unsubscribe_url(user):
    # Signed without a timestamp: the same link for each person, and an old email's link still works. All it can do is turn email alerts off.
    return settings.SITE_URL + reverse("email_unsubscribe", args=[signing.Signer(salt=UNSUBSCRIBE_SALT).sign(str(user.pk))])


EMAILS = {"budget": ("Budget alert", "A budget went over its limit. Sign in to see which one"),
          "bill": ("Bill reminder", "A bill is due soon. Sign in to see which one")}


def email_budget_alert(user_ids, what="budget"):
    """One email per person who turned email alerts on. Generic like push: no budget names, amounts or people
    reach a mailbox. ponytail: sent inline after commit; move to a worker queue when there is one."""
    alerts = settings.SITE_URL + reverse("alerts")
    messages = []
    for user in User.objects.filter(pk__in=user_ids, email_alerts=True).exclude(verified_email=""):
        link = unsubscribe_url(user)
        subject, text = EMAILS[what]
        body = (f"{text}: {alerts}\n\n"
                f"You get this because email alerts are on. Turn them off: {link}\n")
        messages.append(EmailMessage(subject, body, None, [user.verified_email],
                                     headers={"List-Unsubscribe": f"<{link}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}))
    if messages:
        try:
            get_connection().send_messages(messages)
        except (OSError, SMTPException):
            log.warning("Budget alert email failed")
