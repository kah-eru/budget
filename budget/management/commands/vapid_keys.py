from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand
from py_vapid import Vapid01, b64urlencode


class Command(BaseCommand):
    help = "Print a new VAPID key pair for phone push. Put both values in the host's environment; never commit them."

    def handle(self, *args, **options):
        vapid = Vapid01()
        vapid.generate_keys()
        public = vapid.public_key.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        private = vapid.private_key.private_numbers().private_value.to_bytes(32, "big")
        self.stdout.write(f"WEBPUSH_VAPID_PUBLIC_KEY={b64urlencode(public)}\nWEBPUSH_VAPID_PRIVATE_KEY={b64urlencode(private)}")
