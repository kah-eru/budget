from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, Workspace


@receiver(post_save, sender=User)
def create_personal_workspace(sender, instance, created, raw, **kwargs):
    if created and not raw:
        Workspace.objects.create(owner=instance, name="Personal", is_personal=True)
