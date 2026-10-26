"""New administration models; original inventory data models remain unchanged."""
from django.conf import settings
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=160, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    head = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name='headed_flux_departments')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class AdminAudit(models.Model):
    """Application-level append-only audit records for changes in this admin portal."""
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                              related_name='flux_admin_actions')
    action = models.CharField(max_length=80, db_index=True)
    target_type = models.CharField(max_length=80)
    target_id = models.CharField(max_length=80)
    summary = models.CharField(max_length=255)
    changes = models.JSONField(default=dict, blank=True)
    happened_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-happened_at']

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError('Audit entries cannot be edited')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Audit entries cannot be deleted')


class AdminNotification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name='flux_notifications')
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=500)
    # Named internal relative path, never a user-provided off-site redirect.
    link = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    event_key = models.CharField(max_length=140, blank=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['recipient', 'event_key'],
                        condition=~models.Q(event_key=''), name='unique_flux_notification_event')]


class PortalSettings(models.Model):
    institution_name = models.CharField(max_length=180, default='Flux Institution')
    support_email = models.EmailField(blank=True)
    currency = models.CharField(max_length=3, default='GHS')
    date_format = models.CharField(max_length=20, default='d M Y')
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)
