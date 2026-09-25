from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import STANDARD_CATEGORIES, Category, User, Workspace


@receiver(post_save, sender=User)
def create_personal_workspace(sender, instance, created, raw, **kwargs):
    if created and not raw:
        Workspace.objects.create(owner=instance, name="Personal", is_personal=True)


@receiver(post_save, sender=Workspace)
def seed_categories(sender, instance, created, raw, **kwargs):
    if created and not raw:
        Category.objects.bulk_create(Category(workspace=instance, name=name) for name in STANDARD_CATEGORIES)
