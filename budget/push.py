import json
import logging
from urllib.parse import urlsplit

from django.conf import settings
from pywebpush import WebPushException, webpush
from requests import RequestException

from .models import PushSubscription

log = logging.getLogger(__name__)

# Only real browser push services, so a forged endpoint cannot make the server call internal addresses (SSRF).
PUSH_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "web.push.apple.com", "notify.windows.com")
# Generic on purpose: lock screens show this, so no budget names, amounts or people.
ALERT = {"title": "Budget alert", "body": "A budget went over its limit. Open Budget to see which one.", "url": "/alerts/"}


def enabled():
    return bool(settings.WEBPUSH_VAPID_PUBLIC_KEY and settings.WEBPUSH_VAPID_PRIVATE_KEY)


def valid_endpoint(url):
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and parts.port in (None, 443) and any(host == h or host.endswith("." + h) for h in PUSH_HOSTS)


def send_budget_alert(user_ids):
    """One push per subscribed device of each user. Devices the push service reports gone (404/410) are removed.
    ponytail: sent inline after commit with a 5 s timeout per device; move to a worker queue when there is one."""
    if not enabled():
        return
    for sub in PushSubscription.objects.filter(user_id__in=user_ids):
        try:
            webpush(subscription_info={"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
                    data=json.dumps(ALERT), vapid_private_key=settings.WEBPUSH_VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.WEBPUSH_CONTACT}, timeout=5, ttl=86400)
        except WebPushException as error:
            status = getattr(error.response, "status_code", None)
            if status in (404, 410):
                sub.delete()
            else:
                log.warning("Push to a device failed with status %s", status)
        except RequestException:
            log.warning("Push to a device failed to connect")
