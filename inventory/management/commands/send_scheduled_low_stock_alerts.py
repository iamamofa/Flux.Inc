from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

from inventory.low_stock import get_low_stock_alerts
from inventory.email_utils import attach_inline_email_images
from inventory.models import LowStockEmailDelivery, Project, User, UserProfile


RETRY_DELAY = timedelta(minutes=15)
MAX_ATTEMPTS = 8


class Command(BaseCommand):
    help = 'Send scheduled low-stock digests using each recipient’s local time.'

    def handle(self, *args, **options):
        if not settings.EMAIL_HOST_USER:
            raise CommandError(
                'Email is not configured. Set FLUX_EMAIL_USER before running this command.'
            )

        now = timezone.now()
        deliveries_created = self.create_due_deliveries(now)
        sent_count, failed_count = self.process_due_deliveries(now)
        self.stdout.write(
            self.style.SUCCESS(
                f'Created {deliveries_created} scheduled delivery record(s); '
                f'sent {sent_count}; failed {failed_count}.'
            )
        )
        if failed_count:
            raise CommandError(f'{failed_count} low-stock digest delivery attempt(s) failed.')

    def create_due_deliveries(self, now):
        created_count = 0
        projects = Project.objects.filter(is_active=True).select_related(
            'project_manager'
        ).prefetch_related('project_editors', 'project_members')
        for project in projects:
            recipient_ids = set(project.project_editors.values_list('id', flat=True))
            recipient_ids.update(project.project_members.values_list('id', flat=True))
            if project.project_manager_id:
                recipient_ids.add(project.project_manager_id)
            if not recipient_ids or not get_low_stock_alerts(project):
                continue

            recipients = User.objects.filter(
                id__in=recipient_ids,
                is_active=True,
            ).select_related('profile')
            for recipient in recipients:
                if not recipient.email:
                    continue
                try:
                    profile = recipient.profile
                    local_now = now.astimezone(ZoneInfo(profile.time_zone))
                except (UserProfile.DoesNotExist, ZoneInfoNotFoundError, ValueError) as error:
                    self.stderr.write(
                        f'Skipping low-stock schedule for user {recipient.pk}: {error}'
                    )
                    continue

                local_time = local_now.time().replace(second=0, microsecond=0)
                for scheduled_time in {
                    project.low_stock_morning_time,
                    project.low_stock_evening_time,
                }:
                    if local_time < scheduled_time:
                        continue
                    _, created = LowStockEmailDelivery.objects.get_or_create(
                        project=project,
                        recipient=recipient,
                        scheduled_date=local_now.date(),
                        scheduled_time=scheduled_time,
                    )
                    created_count += int(created)
        return created_count

    def process_due_deliveries(self, now):
        sent_count = 0
        failed_count = 0
        retry_before = now - RETRY_DELAY
        deliveries = LowStockEmailDelivery.objects.filter(
            sent_at__isnull=True,
            attempt_count__lt=MAX_ATTEMPTS,
        ).filter(
            Q(last_attempt_at__isnull=True)
            | Q(last_attempt_at__lte=retry_before)
        ).select_related('project', 'recipient').order_by(
            'scheduled_date', 'scheduled_time', 'pk'
        )

        for delivery_id in deliveries.values_list('pk', flat=True):
            if not self.claim_delivery(delivery_id, now, retry_before):
                continue
            delivery = LowStockEmailDelivery.objects.select_related(
                'project', 'recipient'
            ).get(pk=delivery_id)
            alerts = get_low_stock_alerts(delivery.project)
            if not alerts:
                delivery.sent_at = now
                delivery.last_error = ''
                delivery.save(update_fields=['sent_at', 'last_error'])
                continue

            try:
                self.send_digest(delivery, alerts)
            except Exception as error:
                failed_count += 1
                delivery.last_error = str(error)[:4000]
                delivery.save(update_fields=['last_error'])
                self.stderr.write(
                    f'Low-stock digest failed for project {delivery.project_id}, '
                    f'user {delivery.recipient_id}: {error}'
                )
                continue

            delivery.sent_at = now
            delivery.last_error = ''
            delivery.save(update_fields=['sent_at', 'last_error'])
            sent_count += 1
        return sent_count, failed_count

    @staticmethod
    def claim_delivery(delivery_id, now, retry_before):
        with transaction.atomic():
            delivery = LowStockEmailDelivery.objects.select_for_update().filter(
                pk=delivery_id,
                sent_at__isnull=True,
                attempt_count__lt=MAX_ATTEMPTS,
            ).filter(
                Q(last_attempt_at__isnull=True)
                | Q(last_attempt_at__lte=retry_before)
            ).first()
            if delivery is None:
                return False
            delivery.attempt_count += 1
            delivery.last_attempt_at = now
            delivery.save(update_fields=['attempt_count', 'last_attempt_at'])
        return True

    @staticmethod
    def send_digest(delivery, alerts):
        project = delivery.project
        inventory_url = f'{settings.SITE_URL}{alerts[0]["url"]}'
        local_date = delivery.scheduled_date
        profile = delivery.recipient.profile
        zone_name = profile.time_zone
        local_schedule = datetime.combine(
            local_date,
            delivery.scheduled_time,
            tzinfo=ZoneInfo(zone_name),
        )
        context = {
            'project': project,
            'alerts': alerts,
            'inventory_url': inventory_url,
            'scheduled_time': local_schedule.strftime('%H:%M'),
            'time_zone': zone_name,
        }
        subject = f'Low-stock summary for {project.name}'
        message = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(
                'inventory/low_stock_digest_email.txt',
                context,
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.recipient.email],
        )
        message.attach_alternative(
            render_to_string('inventory/low_stock_digest_email.html', context),
            'text/html',
        )
        message.mixed_subtype = 'related'
        attach_inline_email_images(message, ['Bell.png', 'Logo_Orange.png'])
        if message.send(fail_silently=False) != 1:
            raise RuntimeError('Email backend did not confirm a successful delivery.')
