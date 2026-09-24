from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage
from django.test import SimpleTestCase


class PrivateStorageTests(SimpleTestCase):
    def test_default_storage_is_private_and_not_served(self):
        location = Path(default_storage.location).resolve()
        self.assertEqual(location, Path(settings.BUDGET_PRIVATE_STORAGE_ROOT).resolve())
        self.assertFalse(location.is_relative_to(Path(settings.STATIC_ROOT).resolve()))
        self.assertFalse(location.is_relative_to(settings.BASE_DIR / "budget" / "static"))
        self.assertEqual(self.client.get(f"/{settings.MEDIA_URL.strip('/')}/x.pdf".replace("//", "/")).status_code, 404)
