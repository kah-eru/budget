"""Playwright-only local server and synthetic database; never use for personal data."""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="1", BUDGET_LOCAL_SQLITE="1",
                  DJANGO_SECRET_KEY=secrets.token_urlsafe(48), DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost")

import django
from django.conf import settings
from django.core.management import call_command

(ROOT / ".local").mkdir(exist_ok=True)
settings.DATABASES["default"]["NAME"] = ROOT / ".local" / "browser.sqlite3"
settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
django.setup()
call_command("migrate", interactive=False, verbosity=0)

from budget.models import User

user, _ = User.objects.get_or_create(username="browser-check")
user.set_password("synthetic-browser-check-only")
user.save()
sys.stdout = open(ROOT / ".local" / "browser-server.log", "w", encoding="utf-8", buffering=1)
sys.stderr = open(ROOT / ".local" / "browser-server-errors.log", "w", encoding="utf-8", buffering=1)
(ROOT / ".local" / "browser-server.pid").write_text(str(os.getpid()))
call_command("runserver", "127.0.0.1:8000", use_reloader=False)
