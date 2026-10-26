from urllib.parse import urlencode
from datetime import datetime, time, timedelta, timezone as datetime_timezone
import io
import json
from tempfile import TemporaryDirectory
import zipfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.signals import user_logged_in
from django.utils import timezone
from PIL import Image

from .models import (
    Consumable,
    Equipment,
    LowStockEmailDelivery,
    Log,
    MSDSFile,
    ProjectLoginEvent,
    Project,
    Reagent,
    Sample,
    TrashConsumable,
    TrashEquipment,
    TrashSample,
    UserProfile,
)


class ProjectSettingsAccessTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='mega-manager',
            email='manager@example.invalid',
            password='test-password',
        )
        self.member = User.objects.create_user(
            username='mega-member',
            email='member@example.invalid',
            password='test-password',
        )
        self.outsider = User.objects.create_user(
            username='project-outsider',
            email='outsider@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='MEGA 1',
            project_manager=self.manager,
        )
        self.project.project_members.add(self.member)
        self.url = reverse(
            'project_settings',
            kwargs={'project_name': self.project.name},
        )

    def test_settings_redirects_anonymous_users_to_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            f'{reverse("login")}?{urlencode({"next": self.url})}',
            fetch_redirect_response=False,
        )

    def test_project_manager_and_member_can_view_settings(self):
        for user in (self.manager, self.member):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(self.url)

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-flux-density')
                self.assertNotContains(response, 'data-flux-theme')
                self.assertContains(response, 'General &amp; Appearance')
                self.assertContains(response, 'Back to inventory')
                self.assertContains(response, 'Current project')
                self.assertContains(response, 'Inventory Preferences')
                self.assertContains(response, 'Notifications')
                self.assertContains(response, 'Password &amp; Security')
                self.assertContains(response, 'Data &amp; Privacy')
                self.assertContains(response, 'About Flux')
                self.assertContains(response, reverse('change_password'))
                self.assertContains(
                    response,
                    reverse(
                        'export_project_backup',
                        kwargs={'project_name': self.project.name},
                    ),
                )
                sidebar = response.content.decode().split('<main', 1)[0]
                self.assertNotIn('Password &amp; Security', sidebar)
                self.assertContains(response, 'MEGA 1')

    def test_user_can_update_profile_details_and_photo(self):
        self.client.force_login(self.manager)
        picture = io.BytesIO()
        Image.new('RGB', (20, 20), color='blue').save(picture, format='PNG')
        picture.seek(0)

        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            response = self.client.post(self.url, {
                'notification_action': 'profile',
                'username': 'updated-manager',
                'first_name': 'Mega',
                'last_name': 'Manager',
                'email': 'updated-manager@example.invalid',
                'department': 'Research',
                'phone_number': '+1 555 0100',
                'bio': 'I coordinate the MEGA research team.',
                'profile_picture': SimpleUploadedFile(
                    'profile.png',
                    picture.read(),
                    content_type='image/png',
                ),
            })

            self.assertRedirects(
                response,
                self.url,
                fetch_redirect_response=False,
            )
            self.manager.refresh_from_db()
            profile = UserProfile.objects.get(user=self.manager)
            self.assertEqual(self.manager.username, 'updated-manager')
            self.assertEqual(self.manager.first_name, 'Mega')
            self.assertEqual(self.manager.email, 'updated-manager@example.invalid')
            self.assertEqual(profile.department, 'Research')
            self.assertEqual(profile.bio, 'I coordinate the MEGA research team.')
            self.assertTrue(profile.profile_picture.name.startswith('profile_pictures/'))
            self.assertTrue(profile.profile_picture.storage.exists(profile.profile_picture.name))

    def test_profile_rejects_duplicate_username_and_email(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'notification_action': 'profile',
            'username': self.member.username,
            'first_name': 'Changed',
            'last_name': '',
            'email': self.member.email,
            'department': '',
            'phone_number': '',
            'bio': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'That username is already in use.')
        self.assertContains(response, 'That email address is already in use.')
        self.assertContains(response, 'Your profile hasn’t been saved.')
        self.assertContains(response, 'href="#id_email"')
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.username, 'mega-manager')

    def test_manager_sees_project_member_login_history_but_members_do_not(self):
        login_request = RequestFactory().get(
            '/',
            REMOTE_ADDR='203.0.113.42',
            HTTP_USER_AGENT='Flux test browser / test device',
        )
        user_logged_in.send(
            sender=User,
            request=login_request,
            user=self.member,
        )
        login_event = ProjectLoginEvent.objects.filter(
            project=self.project,
            user=self.member,
        ).latest('logged_in_at')
        self.assertIsNotNone(login_event.logged_in_at)
        self.assertEqual(login_event.ip_address, '203.0.113.42')
        self.assertEqual(
            login_event.user_agent,
            'Flux test browser / test device',
        )

        self.client.force_login(self.manager)
        manager_response = self.client.get(self.url)
        self.assertContains(manager_response, 'Team Login History')
        self.assertContains(manager_response, 'mega-member')
        self.assertContains(manager_response, '203.0.113.42')
        self.assertContains(manager_response, 'Flux test browser / test device')

        self.client.force_login(self.member)
        member_response = self.client.get(self.url)
        self.assertNotContains(member_response, 'Team Login History')

    def test_only_project_manager_can_clear_login_history(self):
        ProjectLoginEvent.objects.create(
            project=self.project,
            user=self.member,
            username=self.member.username,
            ip_address='203.0.113.42',
        )
        self.client.force_login(self.member)
        event_count_before_denied_request = ProjectLoginEvent.objects.filter(
            project=self.project
        ).count()

        denied = self.client.post(self.url, {
            'notification_action': 'clear_login_history',
        })
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(ProjectLoginEvent.objects.filter(
            project=self.project
        ).count(), event_count_before_denied_request)

        self.client.force_login(self.manager)
        cleared = self.client.post(self.url, {
            'notification_action': 'clear_login_history',
        })
        self.assertRedirects(cleared, self.url, fetch_redirect_response=False)
        self.assertFalse(ProjectLoginEvent.objects.filter(
            project=self.project
        ).exists())

    def test_manager_login_history_includes_editors(self):
        editor = User.objects.create_user(
            username='mega-editor',
            email='editor@example.invalid',
            password='test-password',
        )
        self.project.project_editors.add(editor)
        user_logged_in.send(
            sender=User,
            request=RequestFactory().get(
                '/',
                REMOTE_ADDR='203.0.113.43',
                HTTP_USER_AGENT='Editor browser',
            ),
            user=editor,
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        self.assertContains(response, 'mega-editor')
        self.assertContains(response, '203.0.113.43')

    def test_project_member_downloads_project_scoped_backup(self):
        Consumable.objects.create(
            project=self.project,
            name='Project consumable',
            items_per_pack=10,
            items_left_in_pack=7,
            pack_count=1,
            cold_storage='Room temperature',
        )
        another_project = Project.objects.create(
            name='Other project',
            project_manager=self.outsider,
        )
        Consumable.objects.create(
            project=another_project,
            name='Private consumable',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
        )
        self.client.force_login(self.member)

        reagent = Reagent.objects.create(
            project=self.project,
            name='Project reagent',
            items_per_pack=5,
            items_left_in_pack=5,
            pack_count=1,
            cold_storage='Room temperature',
        )
        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            MSDSFile.objects.create(
                file=SimpleUploadedFile(
                    'safety-sheet.pdf',
                    b'project MSDS contents',
                    content_type='application/pdf',
                ),
                reagent=reagent,
                uploaded_by=self.manager,
            )
            response = self.client.get(reverse(
                'export_project_backup',
                kwargs={'project_name': self.project.name},
            ))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/zip')
            self.assertIn('attachment;', response['Content-Disposition'])
            self.assertIn('no-store', response['Cache-Control'])
            backup_content = b''.join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(backup_content)) as backup:
            self.assertIn('README.txt', backup.namelist())
            self.assertIn('manifest.json', backup.namelist())
            manifest = json.loads(backup.read('manifest.json'))
            self.assertEqual(manifest['project_name'], self.project.name)
            self.assertEqual(
                next(
                    dataset['record_count']
                    for dataset in manifest['datasets']
                    if dataset['name'] == 'consumables'
                ),
                1,
            )
            consumable_rows = json.loads(backup.read('data/consumables.json'))
            self.assertEqual(len(consumable_rows), 1)
            self.assertEqual(
                consumable_rows[0]['fields']['name'],
                'Project consumable',
            )
            self.assertNotIn(
                'Private consumable',
                backup.read('data/consumables.json').decode(),
            )
            attachment = manifest['attachments'][0]
            self.assertEqual(
                backup.read(attachment['archive_path']),
                b'project MSDS contents',
            )

    def test_nonmember_cannot_download_project_backup(self):
        self.client.force_login(self.outsider)

        response = self.client.get(reverse(
            'export_project_backup',
            kwargs={'project_name': self.project.name},
        ))

        self.assertEqual(response.status_code, 403)

    def test_equipment_add_accepts_csrf_form_token_and_creates_record(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        page = csrf_client.get(reverse(
            'equipment_',
            kwargs={'project_name': self.project.name},
        ))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'equipment_.js?v=6')
        csrf_token = page.cookies['csrftoken'].value

        response = csrf_client.post(
            reverse(
                'add_equipment',
                kwargs={'project_name': self.project.name},
            ),
            {
                'name': 'Centrifuge',
                'equip_id': 'EQ-CSRF-1',
                'quantity': '2',
                'status': 'operational',
                'storage_location': 'Room 1',
            },
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200, response.content)
        equipment = Equipment.objects.get(equip_id='EQ-CSRF-1')
        self.assertEqual(equipment.project, self.project)
        self.assertEqual(equipment.quantity, 2)
        self.assertIsNone(equipment.service_contract_start)
        self.assertIsNone(equipment.service_contract_end)
        self.assertEqual(equipment.donated_by, '')

    def test_equipment_add_returns_field_errors_for_invalid_data(self):
        Equipment.objects.create(
            project=self.project,
            name='Existing equipment',
            equip_id='EQ-DUPLICATE',
        )
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                'add_equipment',
                kwargs={'project_name': self.project.name},
            ),
            {
                'name': 'Duplicate equipment',
                'equip_id': 'EQ-DUPLICATE',
                'quantity': '1',
                'status': 'operational',
                'storage_location': 'Room 1',
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            'equip_id',
            response.json()['errors'],
        )
        self.assertEqual(Equipment.objects.filter(
            project=self.project
        ).count(), 1)

    def test_unrelated_user_cannot_view_project_settings(self):
        self.client.force_login(self.outsider)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response,
            'You don’t have access to this project',
            status_code=403,
        )

    def test_project_manager_can_update_digest_times_and_user_time_zone(self):
        self.client.force_login(self.manager)

        schedule_response = self.client.post(self.url, {
            'notification_action': 'schedule',
            'morning_time': '07:15',
            'evening_time': '18:45',
        })
        self.project.refresh_from_db()
        self.assertRedirects(schedule_response, self.url, fetch_redirect_response=False)
        self.assertEqual(self.project.low_stock_morning_time, time(7, 15))
        self.assertEqual(self.project.low_stock_evening_time, time(18, 45))

        timezone_response = self.client.post(self.url, {
            'notification_action': 'timezone',
            'time_zone': 'America/New_York',
        })
        self.assertRedirects(timezone_response, self.url, fetch_redirect_response=False)
        self.assertEqual(
            UserProfile.objects.get(user=self.manager).time_zone,
            'America/New_York',
        )

    def test_project_member_cannot_update_shared_email_schedule(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {
            'notification_action': 'schedule',
            'morning_time': '08:00',
            'evening_time': '20:00',
        })

        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.low_stock_morning_time, time(6, 0))
        self.assertEqual(self.project.low_stock_evening_time, time(19, 0))

        timezone_response = self.client.post(self.url, {
            'notification_action': 'timezone',
            'time_zone': 'Europe/London',
        })
        self.assertRedirects(timezone_response, self.url, fetch_redirect_response=False)
        self.assertEqual(
            UserProfile.objects.get(user=self.member).time_zone,
            'Europe/London',
        )

    def test_project_editor_can_update_shared_email_schedule(self):
        editor = User.objects.create_user(
            username='mega-editor',
            email='editor@example.invalid',
            password='test-password',
        )
        self.project.project_editors.add(editor)
        self.client.force_login(editor)

        response = self.client.post(self.url, {
            'notification_action': 'schedule',
            'morning_time': '07:00',
            'evening_time': '18:30',
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.project.refresh_from_db()
        self.assertEqual(self.project.low_stock_morning_time, time(7, 0))
        self.assertEqual(self.project.low_stock_evening_time, time(18, 30))

    def test_invalid_recipient_time_zone_is_rejected(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'notification_action': 'timezone',
            'time_zone': 'Not/A-Timezone',
        })

        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertEqual(UserProfile.objects.get(user=self.manager).time_zone, 'UTC')

    def test_settings_displays_save_confirmation(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url, {
            'notification_action': 'timezone',
            'time_zone': 'Africa/Accra',
        }, follow=True)

        self.assertContains(response, 'Your time zone was updated.')
        self.assertContains(response, 'role="status"')

    def test_email_delivery_status_requires_both_credentials(self):
        self.client.force_login(self.manager)

        for email_user, password, configured in (
            ('', '', False),
            ('alerts@example.invalid', '', False),
            ('', 'test-password', False),
            ('alerts@example.invalid', 'test-password', True),
        ):
            with self.subTest(configured=configured, email_user=email_user):
                with override_settings(EMAIL_HOST_USER=email_user, EMAIL_HOST_PASSWORD=password):
                    response = self.client.get(self.url)

                self.assertEqual(response.context['email_alerts_configured'], configured)
                if configured:
                    self.assertContains(response, 'Email delivery is configured.')
                else:
                    self.assertContains(response, 'Contact your system administrator')


class TeamMemberManagementTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='team-manager',
            email='team-manager@example.invalid',
            password='test-password',
        )
        self.member = User.objects.create_user(
            username='team-member',
            email='team-member@example.invalid',
            password='test-password',
        )
        self.outsider = User.objects.create_user(
            username='team-outsider',
            email='team-outsider@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Team Project',
            project_manager=self.manager,
        )
        self.url = reverse(
            'add_user_to_project',
            kwargs={'project_name': self.project.name},
        )
        self.client.force_login(self.manager)

    def test_manager_can_add_a_limited_member_using_ajax(self):
        response = self.client.post(
            self.url,
            {'email': self.member.email, 'role': 'Limited'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'success': True})
        self.assertTrue(self.project.project_members.filter(pk=self.member.pk).exists())
        self.assertTrue(
            UserProfile.objects.get(user=self.member).managed_projects.filter(
                pk=self.project.pk
            ).exists()
        )
        self.assertEqual(self.project.logs.count(), 1)

    def test_member_addition_rejects_unknown_email_and_invalid_role(self):
        for data, expected_status in (
            ({'email': 'missing@example.invalid', 'role': 'Limited'}, 404),
            ({'email': self.member.email, 'role': 'Administrator'}, 400),
        ):
            with self.subTest(data=data):
                response = self.client.post(
                    self.url,
                    data,
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )

                self.assertEqual(response.status_code, expected_status)
                self.assertFalse(response.json()['success'])
        self.assertFalse(self.project.project_members.exists())
        self.assertFalse(self.project.project_editors.exists())

    def test_member_addition_rejects_duplicate_members_and_non_managers(self):
        self.project.project_members.add(self.member)
        response = self.client.post(
            self.url,
            {'email': self.member.email, 'role': 'Limited'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])

        self.client.force_login(self.outsider)
        response = self.client.post(
            self.url,
            {'email': self.outsider.email, 'role': 'Limited'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(self.project.project_members.filter(pk=self.outsider.pk).exists())

    def test_directory_includes_manager_and_deduplicates_editors(self):
        self.project.project_editors.add(self.member)
        self.project.project_members.add(self.member)
        response = self.client.get(reverse('team', args=[self.project.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['team_members']), 2)
        self.assertEqual(response.context['editor_count'], 1)
        self.assertEqual(response.context['limited_count'], 0)
        self.assertContains(response, 'Project owner')

    def test_members_can_view_directory_but_not_management_controls(self):
        self.project.project_members.add(self.member)
        self.client.force_login(self.member)
        response = self.client.get(reverse('team', args=[self.project.name]))
        self.assertContains(response, self.manager.email)
        self.assertNotContains(response, 'data-open-add')
        self.assertNotContains(response, 'data-edit-member')
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(reverse('team', args=[self.project.name])).status_code, 403)

    def test_manager_can_change_access_in_both_directions(self):
        self.project.project_members.add(self.member)
        url = reverse('edit_user_access', args=[self.project.name, self.member.pk])
        for role in ('Full', 'Limited'):
            with self.subTest(role=role):
                response = self.client.post(url, {'role': role})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()['success'])
                self.assertEqual(self.project.project_editors.filter(pk=self.member.pk).exists(), role == 'Full')
                self.assertEqual(self.project.project_members.filter(pk=self.member.pk).exists(), role == 'Limited')
        self.assertEqual(self.project.logs.count(), 2)

    def test_invalid_access_does_not_change_membership(self):
        self.project.project_members.add(self.member)
        url = reverse('edit_user_access', args=[self.project.name, self.member.pk])
        self.assertEqual(self.client.post(url, {'role': 'Manager'}).status_code, 400)
        self.assertTrue(self.project.project_members.filter(pk=self.member.pk).exists())
        self.assertFalse(self.project.logs.exists())

    def test_manager_removal_is_atomic_and_preserves_account(self):
        self.project.project_editors.add(self.member)
        self.project.project_members.add(self.member)
        profile, _ = UserProfile.objects.get_or_create(user=self.member)
        profile.managed_projects.add(self.project)
        response = self.client.post(reverse('remove_user', args=[self.project.name, self.member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertFalse(self.project.project_members.exists())
        self.assertFalse(self.project.project_editors.exists())
        self.assertFalse(profile.managed_projects.filter(pk=self.project.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        self.assertEqual(self.project.logs.count(), 1)

    def test_team_mutations_require_manager_and_post(self):
        self.project.project_members.add(self.member)
        urls = [reverse(name, args=[self.project.name, self.member.pk]) for name in ('remove_user', 'edit_user_access')]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(self.client.put(url, '{}', content_type='application/json').status_code, 405)
                for person in (self.member, self.outsider):
                    self.client.force_login(person)
                    self.assertEqual(self.client.post(url, {'role': 'Full'}).status_code, 403)
                self.client.force_login(self.manager)
        self.assertTrue(self.project.project_members.filter(pk=self.member.pk).exists())

    def test_manager_cannot_be_removed_or_demoted(self):
        for name in ('remove_user', 'edit_user_access'):
            self.assertEqual(self.client.post(reverse(name, args=[self.project.name, self.manager.pk]), {'role': 'Limited'}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'email': self.manager.email, 'role': 'Full'}).status_code, 400)

    def test_non_members_cannot_be_edited_or_removed(self):
        for name in ('remove_user', 'edit_user_access'):
            self.assertEqual(self.client.post(reverse(name, args=[self.project.name, self.outsider.pk]), {'role': 'Full'}).status_code, 404)
        self.assertFalse(self.project.project_editors.exists())

    def test_team_mutations_remain_csrf_protected(self):
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.manager)
        for name in ('remove_user', 'edit_user_access'):
            self.assertEqual(secured.post(reverse(name, args=[self.project.name, self.member.pk]), {'role': 'Full'}).status_code, 403)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST_USER='flux@example.invalid',
    DEFAULT_FROM_EMAIL='flux@example.invalid',
)
class ImmediateLowStockEmailTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='stock-manager',
            email='manager@example.invalid',
            password='test-password',
        )
        self.member = User.objects.create_user(
            username='stock-member',
            email='member@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Stock Alerts',
            project_manager=self.manager,
        )
        self.project.project_members.add(self.member)
        self.client.force_login(self.manager)

    def test_consumable_alert_sends_once_on_entering_low_stock_and_again_after_restock(self):
        consumable = Consumable.objects.create(
            project=self.project,
            name='Pipette tips',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=5,
            cold_storage='Room temperature',
            threshold_value=4,
        )
        url = reverse('retrieve_consumable', kwargs={'consumable_id': consumable.pk})

        response = self.client.post(url, {'retrieve_by': 'Packs', 'amount': 2})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload['low_stock'])
        self.assertTrue(payload['low_stock_alert'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertCountEqual(
            mail.outbox[0].to,
            ['manager@example.invalid', 'member@example.invalid'],
        )
        self.assertIn('Pipette tips', mail.outbox[0].body)
        self.assertIn('3 packs', mail.outbox[0].body)
        self.assertIn('/consumables/Stock%20Alerts/', mail.outbox[0].body)
        html_body = next(
            content for content, content_type in mail.outbox[0].alternatives
            if content_type == 'text/html'
        )
        self.assertIn('src="cid:Bell"', html_body)
        mime_message = mail.outbox[0].message()
        self.assertEqual(mime_message.get_content_subtype(), 'related')
        self.assertTrue(any(
            part.get('Content-ID') == '<Bell>'
            and part.get_content_type() == 'image/png'
            and part.get_content_disposition() == 'inline'
            for part in mime_message.walk()
        ))

        still_low_response = self.client.post(
            url, {'retrieve_by': 'Packs', 'amount': 1}
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(still_low_response.json()['low_stock_alert'])

        restock_url = reverse('return_consumable', kwargs={'consumable_id': consumable.pk})
        self.client.post(restock_url, {'restock_by': 'Packs', 'amount': 2})
        self.client.post(url, {'retrieve_by': 'Packs', 'amount': 1})

        self.assertEqual(len(mail.outbox), 2)

    def test_retrieval_rejects_amounts_above_available_stock_and_handles_exact_depletion(self):
        consumable = Consumable.objects.create(
            project=self.project,
            name='Limited tips',
            items_per_pack=10,
            items_left_in_pack=5,
            pack_count=1,
            cold_storage='Room temperature',
        )
        retrieve_url = reverse(
            'retrieve_consumable',
            kwargs={'consumable_id': consumable.pk},
        )

        too_many_items = self.client.post(
            retrieve_url,
            {'retrieve_by': 'Pack size', 'amount': 6},
        )

        self.assertEqual(too_many_items.status_code, 400)
        self.assertEqual(too_many_items.json()['error'], 'Only 5 items are available')
        consumable.refresh_from_db()
        self.assertEqual(consumable.pack_count, 1)
        self.assertEqual(consumable.items_left_in_pack, 5)

        exact_depletion = self.client.post(
            retrieve_url,
            {'retrieve_by': 'Pack size', 'amount': 5},
        )

        self.assertEqual(exact_depletion.status_code, 200, exact_depletion.content)
        consumable.refresh_from_db()
        self.assertEqual(consumable.pack_count, 0)
        self.assertEqual(consumable.items_left_in_pack, 0)

        no_packs_left = self.client.post(
            retrieve_url,
            {'retrieve_by': 'Quantity', 'amount': 1},
        )
        self.assertEqual(no_packs_left.status_code, 400)
        self.assertEqual(no_packs_left.json()['error'], 'Only 0 packs are available')

    def test_retrieval_rejects_more_full_packs_than_stock_for_reagents(self):
        reagent = Reagent.objects.create(
            project=self.project,
            name='Limited reagent',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
        )
        retrieve_url = reverse(
            'retrieve_reagent',
            kwargs={'reagent_id': reagent.pk},
        )

        response = self.client.post(
            retrieve_url,
            {'retrieve_by': 'Quantity', 'amount': 2},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Only 1 pack are available')
        reagent.refresh_from_db()
        self.assertEqual(reagent.pack_count, 1)
        self.assertEqual(reagent.items_left_in_pack, 10)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST_USER='flux@example.invalid',
    DEFAULT_FROM_EMAIL='flux@example.invalid',
    SITE_URL='https://flux.example.invalid',
)
class ScheduledLowStockEmailTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='scheduled-manager',
            email='scheduled@example.invalid',
            password='test-password',
        )
        self.member = User.objects.create_user(
            username='scheduled-member',
            email='scheduled-member@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Scheduled Stock',
            project_manager=self.manager,
        )
        self.project.project_members.add(self.member)
        profile = UserProfile.objects.get(user=self.manager)
        profile.time_zone = 'America/New_York'
        profile.save(update_fields=['time_zone'])
        profile = UserProfile.objects.get(user=self.member)
        profile.time_zone = 'America/Los_Angeles'
        profile.save(update_fields=['time_zone'])
        Consumable.objects.create(
            project=self.project,
            name='Low stock pipette tips',
            items_per_pack=100,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=2,
        )

    def test_digests_are_sent_at_each_recipients_local_schedule_once(self):
        before_morning = datetime(2026, 10, 22, 9, 59, tzinfo=datetime_timezone.utc)
        morning = datetime(2026, 10, 22, 10, 0, tzinfo=datetime_timezone.utc)
        west_coast_morning = datetime(
            2026, 10, 22, 13, 0, tzinfo=datetime_timezone.utc
        )
        before_evening = datetime(2026, 10, 22, 22, 59, tzinfo=datetime_timezone.utc)
        evening = datetime(2026, 10, 22, 23, 0, tzinfo=datetime_timezone.utc)

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=before_morning,
        ):
            call_command('send_scheduled_low_stock_alerts')
        self.assertEqual(len(mail.outbox), 0)

        for _ in range(2):
            with patch(
                'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
                return_value=morning,
            ):
                call_command('send_scheduled_low_stock_alerts')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Low-stock summary', mail.outbox[0].subject)
        self.assertIn('Low stock pipette tips', mail.outbox[0].body)
        digest_html = next(
            content for content, content_type in mail.outbox[0].alternatives
            if content_type == 'text/html'
        )
        self.assertIn('src="cid:Bell"', digest_html)
        digest_mime = mail.outbox[0].message()
        self.assertEqual(digest_mime.get_content_subtype(), 'related')
        self.assertTrue(any(
            part.get('Content-ID') == '<Bell>'
            and part.get_content_type() == 'image/png'
            and part.get_content_disposition() == 'inline'
            for part in digest_mime.walk()
        ))
        self.assertEqual(
            LowStockEmailDelivery.objects.filter(
                recipient=self.manager,
                scheduled_date='2026-10-22',
                scheduled_time=time(6, 0),
                sent_at__isnull=False,
            ).count(),
            1,
        )

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=west_coast_morning,
        ):
            call_command('send_scheduled_low_stock_alerts')
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[1].to, ['scheduled-member@example.invalid'])
        self.assertEqual(
            LowStockEmailDelivery.objects.filter(
                recipient=self.member,
                scheduled_date='2026-10-22',
                scheduled_time=time(6, 0),
                sent_at__isnull=False,
            ).count(),
            1,
        )

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=before_evening,
        ):
            call_command('send_scheduled_low_stock_alerts')
        self.assertEqual(len(mail.outbox), 2)

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=evening,
        ):
            call_command('send_scheduled_low_stock_alerts')
        self.assertEqual(len(mail.outbox), 3)
        self.assertEqual(
            LowStockEmailDelivery.objects.filter(
                scheduled_date='2026-10-22',
                sent_at__isnull=False,
            ).count(),
            3,
        )

    def test_failed_delivery_is_reported_and_retried_after_fifteen_minutes(self):
        morning = datetime(2026, 10, 22, 10, 0, tzinfo=datetime_timezone.utc)
        retry_early = datetime(2026, 10, 22, 10, 14, tzinfo=datetime_timezone.utc)
        retry_due = datetime(2026, 10, 22, 10, 15, tzinfo=datetime_timezone.utc)

        with (
            patch(
                'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
                return_value=morning,
            ),
            patch(
                'inventory.management.commands.send_scheduled_low_stock_alerts.Command.send_digest',
                side_effect=RuntimeError('SMTP unavailable'),
            ),
        ):
            with self.assertRaises(CommandError):
                call_command('send_scheduled_low_stock_alerts')

        delivery = LowStockEmailDelivery.objects.get(
            recipient=self.manager,
            scheduled_date='2026-10-22',
            scheduled_time=time(6, 0),
        )
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(delivery.last_error, 'SMTP unavailable')

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=retry_early,
        ):
            call_command('send_scheduled_low_stock_alerts')
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNone(delivery.sent_at)

        with patch(
            'inventory.management.commands.send_scheduled_low_stock_alerts.timezone.now',
            return_value=retry_due,
        ):
            call_command('send_scheduled_low_stock_alerts')
        delivery.refresh_from_db()
        self.assertEqual(delivery.attempt_count, 2)
        self.assertIsNotNone(delivery.sent_at)

    @override_settings(EMAIL_HOST_USER='')
    def test_command_reports_missing_smtp_configuration(self):
        with self.assertRaisesMessage(CommandError, 'Email is not configured'):
            call_command('send_scheduled_low_stock_alerts')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST_USER='flux@example.invalid',
    DEFAULT_FROM_EMAIL='flux@example.invalid',
)
class AdditionalImmediateLowStockEmailTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='stock-manager',
            email='manager@example.invalid',
            password='test-password',
        )
        self.member = User.objects.create_user(
            username='stock-member',
            email='member@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Stock Alerts',
            project_manager=self.manager,
        )
        self.project.project_members.add(self.member)
        self.client.force_login(self.manager)

    def test_reagent_low_stock_alert_uses_reagent_details(self):
        reagent = Reagent.objects.create(
            project=self.project,
            name='Buffer solution',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=3,
            cold_storage='Room temperature',
            threshold_value=3,
        )
        url = reverse('retrieve_reagent', kwargs={'reagent_id': reagent.pk})

        response = self.client.post(url, {'retrieve_by': 'Packs', 'amount': 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Low stock alert: Buffer solution')
        self.assertIn('Reagent', mail.outbox[0].body)
        self.assertIn('/reagents/Stock%20Alerts/', mail.outbox[0].body)

    def test_new_consumable_below_threshold_sends_alert(self):
        url = reverse('add_consumable', kwargs={'project_name': self.project.name})

        response = self.client.post(url, {
            'name': 'Low stock at intake',
            'product_code': 'LOW-1',
            'items_per_pack': 10,
            'pack_count': 1,
            'threshold_value': 2,
            'cold_storage': 'Room temperature',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Low stock at intake', mail.outbox[0].body)

    def test_sample_low_stock_alert_is_sent_when_volume_crosses_threshold(self):
        sample = Sample.objects.create(
            project=self.project,
            sample_id='SAMPLE-1',
            sample_type='Blood',
            volume=6,
            volume_unit='mL',
            collection_date='2026-10-20',
            threshold_value=5,
            notes='',
        )
        url = reverse('retrieve_sample', kwargs={'sample_id': sample.pk})

        response = self.client.post(url, {'amount': 2})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('SAMPLE-1', mail.outbox[0].body)
        self.assertIn('4.00 mL', mail.outbox[0].body)
        self.assertIn('/samples/Stock%20Alerts/', mail.outbox[0].body)

    def test_null_threshold_does_not_break_consumable_retrieval_or_send_email(self):
        consumable = Consumable.objects.create(
            project=self.project,
            name='No threshold item',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=None,
        )
        url = reverse('retrieve_consumable', kwargs={'consumable_id': consumable.pk})

        response = self.client.post(url, {'retrieve_by': 'Packs', 'amount': 1})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_low_stock_consumable_page_shows_in_app_alert_and_red_stock_marker(self):
        Consumable.objects.create(
            project=self.project,
            name='Low stock marker',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=2,
        )

        response = self.client.get(
            reverse('consumables', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Low stock alert')
        self.assertContains(response, 'Low stock marker')
        self.assertContains(response, 'low-stock-row')
        self.assertContains(response, 'low-stock-indicator')


class LowStockAlertVisibilityTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='alert-manager',
            email='alert-manager@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Alert Project',
            project_manager=self.manager,
        )
        self.client.force_login(self.manager)
        Consumable.objects.create(
            project=self.project,
            name='Low consumable',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=2,
        )
        Reagent.objects.create(
            project=self.project,
            name='Low reagent',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=2,
        )
        Sample.objects.create(
            project=self.project,
            sample_id='LOW-SAMPLE',
            sample_type='Blood',
            volume=2,
            volume_unit='mL',
            collection_date='2026-10-20',
            threshold_value=5,
            notes='',
        )

    def test_project_low_stock_alerts_appear_on_each_inventory_and_dashboard(self):
        routes = (
            'consumables',
            'reagents',
            'equipment_',
            'samples',
            'dashboard_consumables',
            'dashboard_reagents',
            'dashboard_equipment_',
            'dashboard_samples',
        )
        for route_name in routes:
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(route_name, kwargs={'project_name': self.project.name})
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Low stock alert')
                self.assertContains(response, '3 items need restocking.')
                self.assertContains(response, 'Low consumable')
                self.assertContains(response, 'Low reagent')
                self.assertContains(response, 'LOW-SAMPLE')
                self.assertContains(response, '1 packs remaining')
                self.assertContains(response, '2.00 mL remaining')
                for route_name in ('consumables', 'reagents', 'samples'):
                    href = reverse(
                        route_name,
                        kwargs={'project_name': self.project.name},
                    )
                    self.assertContains(response, f'href="{href}"')


class DashboardChartDataTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username='dashboard-manager',
            email='dashboard@example.invalid',
            password='test-password',
        )
        self.project = Project.objects.create(
            name='Dashboard Charts',
            project_manager=self.manager,
        )
        self.client.force_login(self.manager)

    def test_inventory_add_and_delete_popups_use_expected_containers(self):
        Consumable.objects.create(
            project=self.project,
            name='Clickable consumable',
            items_per_pack=10,
            items_left_in_pack=10,
            cold_storage='Room temperature',
        )
        Reagent.objects.create(
            project=self.project,
            name='Clickable reagent',
            items_per_pack=10,
            items_left_in_pack=10,
            cold_storage='Room temperature',
        )
        Equipment.objects.create(
            project=self.project,
            name='Clickable equipment',
            equip_id='CLICK-EQ-1',
        )
        Sample.objects.create(
            project=self.project,
            sample_id='CLICK-SAMPLE-1',
            sample_type='Blood',
            volume=10,
            collection_date='2026-10-20',
            notes='',
        )

        add_button_ids = {
            'consumables': 'showAddPopupBtn',
            'reagents': 'addItemBtn',
            'equipment_': 'addItemBtn',
            'samples': 'addItemBtn',
        }
        for route_name, add_button_id in add_button_ids.items():
            with self.subTest(route=route_name):
                response = self.client.get(
                    reverse(route_name, kwargs={'project_name': self.project.name})
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'id="addPopup"')
                self.assertContains(response, f'id="{add_button_id}"')
                self.assertContains(response, 'showInventoryPopup')
                self.assertContains(response, 'flux_design_system.css?v=7')
                self.assertContains(response, 'id="stockActionDialog"')
                self.assertContains(response, 'data-stock-action="remove"')
                self.assertContains(response, 'data-stock-action="add"')
                self.assertContains(response, 'data-stock-item')
                self.assertContains(response, "popup.style.setProperty('display', 'flex', 'important')")
                self.assertContains(
                    response,
                    f"onclick=\"showInventoryPopup('addPopup')\"",
                )
                self.assertRegex(
                    response.content.decode(),
                    r'class="popup-container5"[^>]*id="deletePopup"',
                )

    def test_consumable_dashboard_renders_stock_health_expiry_and_vendor_charts(self):
        Consumable.objects.create(
            project=self.project,
            name='Low stock tips',
            vendor='Lab Supply Co',
            items_per_pack=10,
            items_left_in_pack=10,
            pack_count=1,
            cold_storage='Room temperature',
            threshold_value=3,
            expiry_date=timezone.localdate() + timedelta(days=1),
        )

        response = self.client.get(
            reverse('dashboard_consumables', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        chart_data = response.context['chart_data']
        self.assertEqual(chart_data['category'], 'stock')
        self.assertEqual(chart_data['primary_values'], [1])
        self.assertEqual(chart_data['distribution_values'], [1, 0, 0])
        self.assertEqual(chart_data['secondary_values'][1], 1)
        self.assertEqual(chart_data['tertiary_labels'], ['Lab Supply Co'])
        self.assertContains(response, 'dashboardPrimaryChart')
        self.assertContains(response, 'dashboardDistributionChart')
        self.assertContains(response, 'dashboardSecondaryChart')
        self.assertContains(response, 'dashboardTertiaryChart')
        self.assertContains(response, 'dashboard-sidebar-toggle')
        self.assertContains(response, 'aria-controls="dashboardSidebar"')

    def test_reagent_dashboard_uses_reagent_stock_and_threshold(self):
        Reagent.objects.create(
            project=self.project,
            name='Buffer',
            items_per_pack=20,
            items_left_in_pack=20,
            pack_count=2,
            cold_storage='Room temperature',
            threshold_value=2,
        )

        response = self.client.get(
            reverse('dashboard_reagents', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['chart_data']['category'], 'stock')
        self.assertEqual(response.context['chart_data']['primary_thresholds'], [2])
        self.assertContains(response, 'dashboard-sidebar-toggle')

    def test_equipment_dashboard_uses_equipment_status_and_calibration_instead_of_quantity(self):
        Equipment.objects.create(
            project=self.project,
            name='Centrifuge',
            equip_id='EQ-1',
            status='operational',
            source='Lab purchase',
            next_calibration_date='2026-11-10',
        )

        response = self.client.get(
            reverse('dashboard_equipment_', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        chart_data = response.context['chart_data']
        self.assertEqual(chart_data['category'], 'equipment')
        self.assertEqual(chart_data['primary_values'][0], 1)
        self.assertEqual(chart_data['secondary_values'][1], 1)
        self.assertEqual(chart_data['tertiary_labels'], ['Lab purchase'])
        self.assertContains(response, 'dashboard-sidebar-toggle')

    def test_samples_dashboard_uses_sample_volume_health_type_and_country(self):
        Sample.objects.create(
            project=self.project,
            sample_id='SAMPLE-CHART',
            sample_type='Blood',
            country='Ghana',
            volume=2,
            volume_unit='mL',
            collection_date='2026-10-20',
            threshold_value=5,
            notes='',
        )

        response = self.client.get(
            reverse('dashboard_samples', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        chart_data = response.context['chart_data']
        self.assertEqual(chart_data['category'], 'samples')
        self.assertEqual(chart_data['primary_values'], [2.0])
        self.assertEqual(chart_data['distribution_values'], [1, 0, 0])
        self.assertEqual(chart_data['tertiary_labels'], ['Ghana'])
        self.assertContains(response, 'dashboard-sidebar-toggle')

    def test_low_stock_sample_page_shows_in_app_alert_and_red_volume_marker(self):
        Sample.objects.create(
            project=self.project,
            sample_id='LOW-SAMPLE',
            sample_type='Blood',
            volume=2,
            volume_unit='mL',
            collection_date='2026-10-20',
            threshold_value=5,
            notes='',
        )

        response = self.client.get(
            reverse('samples', kwargs={'project_name': self.project.name})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Low stock alert')
        self.assertContains(response, 'LOW-SAMPLE')
        self.assertContains(response, 'low-stock-row')
        self.assertContains(response, 'low-stock-indicator')
        self.assertContains(response, 'id="sample-form"', count=1)


class WorkspacePageWorkflowTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user('page-manager', 'manager@example.invalid', 'test-password')
        self.member = User.objects.create_user('page-member', 'member@example.invalid', 'test-password')
        self.project = Project.objects.create(name='Page Project', project_manager=self.manager)
        self.project.project_members.add(self.member)
        self.client.force_login(self.manager)

    def test_public_pages_render_and_invalid_login_preserves_email(self):
        self.client.logout()
        for route in ('home', 'login', 'registration_page', 'register_user', 'register_project_manager', 'user_application'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<h1')
                self.assertContains(response, 'flux_pages.css')
        response = self.client.post(reverse('login'), {'email': 'remember@example.invalid', 'password': 'incorrect'})
        self.assertContains(response, 'Invalid credentials.')
        self.assertContains(response, 'value="remember@example.invalid"')

    def test_dashboard_create_project_form_posts_and_returns_inventory_url(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.manager)
        page = csrf_client.get(reverse('dashboard_consumables', kwargs={'project_name': self.project.name}))
        self.assertContains(page, 'js/dashboard.js')
        self.assertContains(page, 'action="/create_project/"')
        response = csrf_client.post(reverse('create_project'), {
            'project_name': 'New project & team',
            'csrfmiddlewaretoken': page.cookies['csrftoken'].value,
        })
        self.assertEqual(response.status_code, 200)
        project = Project.objects.get(name='New project & team')
        self.assertEqual(project.project_manager, self.manager)
        self.assertEqual(response.json()['redirect'], reverse('consumables', kwargs={'project_name': project.name}))
        self.assertTrue(UserProfile.objects.get(user=self.manager).managed_projects.filter(pk=project.pk).exists())

    def test_project_name_errors_do_not_create_records(self):
        before = Project.objects.count()
        for name in ('', '   ', 'Invalid/project', self.project.name):
            with self.subTest(name=name):
                response = self.client.post(reverse('create_project'), {'project_name': name})
                self.assertEqual(response.status_code, 400)
                self.assertIn('error', response.json())
        self.assertEqual(Project.objects.count(), before)

    def archived_consumable(self):
        return TrashConsumable.objects.create(
            project=self.project, original_id='previous-record', name='Archived tips',
            items_per_pack=10, items_left_in_pack=5, pack_count=2,
            date_recorded=timezone.localdate(), cold_storage='Room',
        )

    def test_archive_pages_render_real_records_and_correct_equipment_category(self):
        item = self.archived_consumable()
        equipment = TrashEquipment.objects.create(
            project=self.project, original_id='old-equipment', name='Archived centrifuge',
            equip_id='ARCH-001', status='operational', date_installed=timezone.localdate(),
        )
        response = self.client.get(reverse('trash_consumables', kwargs={'project_name': self.project.name}))
        self.assertContains(response, item.name)
        self.assertContains(response, reverse('restore_trash_consumable', kwargs={'project_name': self.project.name, 'trash_id': item.pk}))
        response = self.client.get(reverse('trash_equipment_', kwargs={'project_name': self.project.name}))
        self.assertContains(response, equipment.name)
        self.assertNotContains(response, item.name)
        for route in ('trash_reagents', 'trash_samples'):
            response = self.client.get(reverse(route, kwargs={'project_name': self.project.name}))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Nothing in this category’s trash')

    def test_restore_consumable_uses_inventory_fields_and_removes_archive(self):
        item = self.archived_consumable()
        response = self.client.post(reverse('restore_trash_consumable', kwargs={'project_name': self.project.name, 'trash_id': item.pk}))
        self.assertEqual(response.status_code, 200, response.content)
        restored = Consumable.objects.get(name=item.name, project=self.project)
        self.assertEqual(restored.pack_count, 2)
        self.assertFalse(TrashConsumable.objects.filter(pk=item.pk).exists())

    def test_archive_mutations_require_post_and_project_management_access(self):
        item = self.archived_consumable()
        routes = (
            reverse('restore_trash_consumable', kwargs={'project_name': self.project.name, 'trash_id': item.pk}),
            reverse('delete_trash_consumable', kwargs={'trash_id': item.pk}),
            reverse('delete_all_consumables_in_trash', kwargs={'project_name': self.project.name}),
        )
        for url in routes:
            self.assertEqual(self.client.get(url).status_code, 405)
        self.client.force_login(self.member)
        for url in routes:
            self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(TrashConsumable.objects.filter(pk=item.pk).exists())

    def test_legacy_sample_restore_preserves_archive_when_required_data_is_missing(self):
        item = TrashSample.objects.create(
            project=self.project, original_id='archived-sample', sample_id='ARCH-SAMPLE',
            sample_type='Blood', date_recorded=timezone.localdate(),
        )
        response = self.client.post(reverse('restore_trash_sample', kwargs={'project_name': self.project.name, 'trash_id': item.pk}))
        self.assertEqual(response.status_code, 400)
        self.assertIn('collection date', response.json()['error'])
        self.assertTrue(TrashSample.objects.filter(pk=item.pk).exists())

    def test_activity_history_is_paginated(self):
        Log.objects.bulk_create([
            Log(project=self.project, user=self.manager, action=f'Inventory update {index}')
            for index in range(55)
        ])
        response = self.client.get(reverse('log', kwargs={'project_name': self.project.name}))
        self.assertEqual(len(response.context['logs']), 50)
        self.assertContains(response, '?page=2')
        response = self.client.get(reverse('log', kwargs={'project_name': self.project.name}), {'page': '2'})
        self.assertEqual(len(response.context['logs']), 5)
