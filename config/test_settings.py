import os

os.environ.setdefault("DJANGO_SECRET_KEY", "synthetic-tests-only-not-a-deployment-secret")
os.environ["DJANGO_DEBUG"] = "1"
os.environ.setdefault("BUDGET_LOCAL_SQLITE", "1")

from .settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
