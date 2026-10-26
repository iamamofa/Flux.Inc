"""Generate notification records from actual registration events."""
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from inventory.models import UserApplication


@receiver(post_save, sender=UserApplication, dispatch_uid='flux_admin_application_notification')
def application_received(sender, instance, created, raw=False, **kwargs):
    if raw or not created:
        return
    pk, label = instance.pk, f'{instance.first_name} {instance.last_name}'.strip()

    def deliver():
        from .views import notify_staff
        notify_staff('New registration application',
                     f'{label} submitted an account application.',
                     reverse('control:overview'), permission='inventory.view_userapplication',
                     event_key=f'application-created-{pk}')

    transaction.on_commit(deliver)
