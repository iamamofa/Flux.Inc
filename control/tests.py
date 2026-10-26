from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from inventory.models import Project, UserProfile
from .models import Department, AdminAudit, AdminNotification

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class PortalTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('root', 'root@example.org', 'PassWord!517#secure')
        self.viewer = User.objects.create_user('viewer', 'viewer@example.org', 'PassWord!517#secure', is_staff=True)
        self.person = User.objects.create_user('researcher', 'researcher@example.org', 'PassWord!517#secure')
        self.client.force_login(self.admin)

    def test_routes_render_with_empty_data(self):
        paths = ['overview', 'users', 'roles', 'departments', 'notifications',
                 'reports', 'audit', 'settings', 'security', 'profile', 'search']
        for route in paths:
            with self.subTest(route=route):
                r = self.client.get(reverse('control:' + route))
                self.assertEqual(r.status_code, 200)
                self.assertContains(r, 'FLUX')

    def test_django_admin_home_uses_flux_branding_and_shortcuts(self):
        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'FLUX')
        self.assertContains(response, 'Administration, at a glance.')
        self.assertContains(response, 'Research projects')
        self.assertContains(response, 'User accounts')
        self.assertContains(response, 'Open Admin Workspace')
        self.assertContains(response, 'admin/css/flux_admin.css')
        self.assertContains(response, 'admin/css/flux_admin.css?v=9')
        self.assertContains(response, 'flux-admin-dashboard-grid')
        self.assertContains(response, 'Recent actions')

    def test_django_admin_login_uses_light_flux_styles(self):
        self.client.logout()
        response = self.client.get(reverse('admin:login'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class=" login"')
        self.assertContains(response, 'admin/css/flux_admin.css?v=9')

    def test_admin_sidebar_shows_only_dashboards_for_accessible_projects(self):
        project = Project.objects.create(name='Admin Dashboard Project', project_manager=self.person)
        project.project_members.add(self.admin)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboards')
        self.assertContains(response, 'Administrator overview')
        self.assertContains(response, 'Admin Dashboard Project')
        self.assertContains(
            response,
            reverse('dashboard_consumables', kwargs={'project_name': project.name}),
        )
        self.assertContains(
            response,
            reverse('dashboard_reagents', kwargs={'project_name': project.name}),
        )
        self.assertContains(
            response,
            reverse('dashboard_equipment_', kwargs={'project_name': project.name}),
        )
        self.assertContains(
            response,
            reverse('dashboard_samples', kwargs={'project_name': project.name}),
        )

    def test_django_admin_inventory_lists_render_with_searchable_columns(self):
        for model_name in ('consumable', 'reagent', 'equipment', 'sample'):
            with self.subTest(model=model_name):
                response = self.client.get(
                    reverse(f'admin:inventory_{model_name}_changelist')
                )

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Flux administration')
                self.assertContains(response, 'Search')

    def test_control_overview_loads_light_flux_dashboard_styles(self):
        response = self.client.get(reverse('control:overview'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'control/portal_refined.css?v=4')
        self.assertContains(response, 'Administrator overview')

    def test_overview_metrics_link_to_their_own_record_lists(self):
        response = self.client.get(reverse('control:overview'))
        stats = {stat['title']: stat for stat in response.context['stats']}
        self.assertEqual(stats['Active accounts']['url'], reverse('control:users') + '?status=active')
        self.assertEqual(stats['Pending registrations']['url'], reverse('admin:inventory_userapplication_changelist') + '?is_approved__exact=0')
        self.assertEqual({item['url'] for item in response.context['inventory_summary']}, {
            reverse(f'admin:inventory_{model}_changelist') for model in ('consumable', 'reagent', 'equipment', 'sample')
        })
        self.assertTrue(all(month['height'] == 0 for month in response.context['registration_months'] if month['value'] == 0))

    def test_overview_inventory_respects_each_model_permission(self):
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_project', content_type__app_label='inventory'))
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('control:overview'))
        self.assertEqual(response.context['inventory_summary'], [])
        self.assertNotContains(response, 'User registrations')
        self.assertNotContains(response, 'Recent administration activity')
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_reagent', content_type__app_label='inventory'))
        response = self.client.get(reverse('control:overview'))
        self.assertEqual([item['url'] for item in response.context['inventory_summary']], [reverse('admin:inventory_reagent_changelist')])

    def test_overview_project_totals_include_manager_and_editors(self):
        project = Project.objects.create(name='Shared research', project_manager=self.person)
        project.project_members.add(self.viewer)
        project.project_editors.add(self.viewer, self.admin)
        response = self.client.get(reverse('control:overview'))
        self.assertEqual(response.context['recent_projects'][0].members_count, 3)
        self.assertContains(response, reverse('admin:inventory_project_change', args=[project.pk]))

    def test_admin_library_and_shortcuts_hide_unavailable_records(self):
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_project', content_type__app_label='inventory'))
        self.client.force_login(self.viewer)
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Find your starting point')
        self.assertContains(response, reverse('admin:inventory_project_changelist'))
        self.assertNotContains(response, reverse('admin:auth_user_changelist'))
        self.assertNotContains(response, reverse('admin:inventory_project_add'))

    def test_admin_project_form_uses_workflow_sections(self):
        response = self.client.get(reverse('admin:inventory_project_add'))
        self.assertContains(response, 'Team &amp; access')
        self.assertContains(response, 'Low-stock notification schedule')

    def test_anonymous_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('control:overview'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login')))

    def test_nonstaff_denied(self):
        self.client.force_login(self.person)
        self.assertEqual(self.client.get(reverse('control:overview')).status_code, 403)
        self.assertEqual(self.client.get(reverse('control:users')).status_code, 403)
        self.assertEqual(self.client.get(reverse('control:report_csv', args=['users'])).status_code, 403)

    def test_staff_requires_object_permissions(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('control:users')).status_code, 403)
        self.viewer.user_permissions.add(Permission.objects.get(codename='view_user', content_type__app_label='auth'))
        self.assertEqual(self.client.get(reverse('control:users')).status_code, 200)
        self.assertEqual(self.client.get(reverse('control:user_create')).status_code, 403)

    def test_user_create_persists_and_logs(self):
        Department.objects.create(name='Bacteriology', code='bacteriology')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('control:user_create'), {
            'username': 'newlab', 'first_name': 'Lab', 'last_name': 'Member',
            'email': 'newlab@example.org', 'department': 'Bacteriology',
            'password1': 'AStrongpass!295', 'password2': 'AStrongpass!295',
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username='newlab')
        self.assertTrue(user.check_password('AStrongpass!295'))
        self.assertEqual(user.profile.department, 'Bacteriology')
        self.assertEqual(AdminAudit.objects.filter(action='user.created', target_id=str(user.pk)).count(), 1)
        self.assertEqual(AdminNotification.objects.filter(recipient=self.admin, event_key=f'account-created-{user.pk}').count(), 1)

    def test_email_uniqueness_validation(self):
        response = self.client.post(reverse('control:user_create'), {
            'username': 'secondlab', 'email': 'researcher@example.org',
            'password1': 'AStrongpass!295', 'password2': 'AStrongpass!295',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already belongs')
        self.assertFalse(User.objects.filter(username='secondlab').exists())

    def test_user_update_reuses_profile(self):
        Department.objects.create(name='Virology', code='virology')
        response = self.client.post(reverse('control:user_edit', args=[self.person.pk]), {
            'username': 'researcher', 'email': 'researcher@example.org',
            'first_name': 'A', 'last_name': 'Scientist', 'department': 'Virology',
        })
        self.assertEqual(response.status_code, 302)
        self.person.refresh_from_db()
        self.assertEqual(self.person.first_name, 'A')
        self.assertEqual(UserProfile.objects.get(user=self.person).department, 'Virology')

    def test_superadministrator_cannot_disable_self(self):
        response = self.client.post(reverse('control:user_status', args=[self.admin.pk]), {'action': 'deactivate'})
        self.assertEqual(response.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_staff_cannot_modify_other_admin_or_roles(self):
        self.viewer.user_permissions.add(Permission.objects.get(codename='change_user', content_type__app_label='auth'))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('control:user_edit', args=[self.admin.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('control:user_status', args=[self.admin.pk]), {'action':'deactivate'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('control:role_create')).status_code, 403)

    def test_department_persists_and_records_audit(self):
        response = self.client.post(reverse('control:department_create'), {
            'name': 'Genomics', 'code': 'genomics', 'head': '', 'description': 'Research', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Department.objects.get(code='genomics').name, 'Genomics')
        self.assertEqual(AdminAudit.objects.filter(action='department.created').count(), 1)

    def test_notifications_private_and_post_only(self):
        notification = AdminNotification.objects.create(recipient=self.admin, title='Test', message='Hi')
        link = reverse('control:notification_read', args=[notification.pk])
        self.assertEqual(self.client.get(link).status_code, 405)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(link).status_code, 302)
        notification.refresh_from_db()
        self.assertIsNone(notification.read_at)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(link).status_code, 302)
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_csv_export_escapes_formula_and_requires_permission(self):
        self.person.first_name = '=HYPERLINK(1)'
        self.person.save(update_fields=['first_name'])
        result = self.client.get(reverse('control:report_csv', args=['users']))
        self.assertEqual(result.status_code, 200)
        self.assertIn("'=HYPERLINK(1)", result.content.decode('utf-8-sig'))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse('control:report_csv', args=['users'])).status_code, 403)

    def test_reports_reject_invalid_date_ranges(self):
        path = reverse('control:report_csv', args=['users'])
        self.assertEqual(self.client.get(path, {'from': 'bad'}).status_code, 400)
        self.assertEqual(self.client.get(path, {'from':'2026-12-01', 'to':'2026-01-01'}).status_code, 400)
        self.assertEqual(self.client.get(path, {'from':'2026-01-01', 'to':'2026-12-01'}).status_code, 200)

    def test_role_assignment_superadmin_only(self):
        group = Group.objects.create(name='Laboratory reader')
        self.assertEqual(self.client.post(reverse('control:assign_role', args=[self.person.pk]),
                                          {'group': group.pk, 'action': 'add'}).status_code, 302)
        self.assertTrue(self.person.groups.filter(pk=group.pk).exists())
        self.assertEqual(self.client.post(reverse('control:assign_role', args=[self.person.pk]),
                                          {'group': group.pk, 'action': 'remove'}).status_code, 302)
        self.assertFalse(self.person.groups.filter(pk=group.pk).exists())

    def test_audit_is_append_only_via_model_api(self):
        entry = AdminAudit.objects.create(actor=self.admin, action='test', target_type='T', target_id='1', summary='Test')
        with self.assertRaises(ValueError):
            entry.save()
        with self.assertRaises(ValueError):
            entry.delete()

    def test_staff_grant_only_superuser(self):
        link = reverse('control:user_staff_access', args=[self.person.pk])
        self.assertEqual(self.client.post(link, {'action': 'grant'}).status_code, 302)
        self.person.refresh_from_db()
        self.assertTrue(self.person.is_staff)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.post(link, {'action': 'revoke'}).status_code, 403)

    @override_settings(EMAIL_HOST_USER='', EMAIL_HOST_PASSWORD='')
    def test_password_recovery_without_email_config_refuses(self):
        result = self.client.post(reverse('control:request_password_reset', args=[self.person.pk]))
        self.assertEqual(result.status_code, 302)
        self.assertFalse(AdminAudit.objects.filter(action='user.password_reset_requested').exists())

    @override_settings(EMAIL_HOST_USER='noreply@example.org', EMAIL_HOST_PASSWORD='configured',
                       EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_sends_real_django_token(self):
        from django.core import mail
        link = reverse('control:request_password_reset', args=[self.person.pk])
        result = self.client.post(link)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/control/auth/reset/', mail.outbox[0].body)
        self.assertTrue(AdminAudit.objects.filter(action='user.password_reset_requested').exists())

    def test_notification_deduplication(self):
        from .views import notify_user
        notify_user(self.admin, 'Event', 'Message', event_key='event-99')
        notify_user(self.admin, 'Event', 'Message', event_key='event-99')
        self.assertEqual(AdminNotification.objects.filter(recipient=self.admin, event_key='event-99').count(), 1)

    def test_original_project_models_remain_available(self):
        project = Project.objects.create(name='Original project', project_manager=self.person)
        response = self.client.get(reverse('control:overview'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Original project')


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'])
class PortalPageFeedbackTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('page-admin', 'admin@example.invalid', 'test-password')
        self.client.force_login(self.admin)

    def test_unread_notifications_keep_filter_when_paginating(self):
        AdminNotification.objects.bulk_create([
            AdminNotification(recipient=self.admin, title=f'Update {number}', message='Project update')
            for number in range(21)
        ])
        response = self.client.get(reverse('control:notifications'), {'filter': 'unread'})
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'page=2&amp;filter=unread', html=False)

    def test_invalid_department_form_displays_field_links(self):
        response = self.client.post(reverse('control:department_create'), {'name': '', 'code': ''})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your changes haven’t been saved.')
        self.assertContains(response, 'href="#id_name"')

    def test_read_only_settings_disable_editing_controls(self):
        viewer = User.objects.create_user('settings-reader', is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename='view_portalsettings'))
        self.client.force_login(viewer)
        response = self.client.get(reverse('control:settings'))
        self.assertContains(response, 'class="form-readonly" disabled')
        self.assertNotContains(response, 'Save settings')


@override_settings(ALLOWED_HOSTS=['testserver', 'localhost'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdministrationWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from datetime import date
        from inventory.models import Rooms, Storages, Shelf, Rack, Box, Sample, Sample_Locations, Consumable

        cls.root = User.objects.create_superuser('workspace-root', 'root@example.invalid', 'test-password')
        cls.member = User.objects.create_user('workspace-member', 'member@example.invalid', 'test-password')
        cls.project = Project.objects.create(name='Workspace project', project_manager=cls.root)
        cls.department = Department.objects.create(name='Genomics', code='gen', head=cls.member)
        profile, _ = UserProfile.objects.get_or_create(user=cls.member)
        profile.department = cls.department.name
        profile.save()
        room = Rooms.objects.create(room_name='Lab A', building='Research wing')
        storage = Storages.objects.create(room_id=room, storage_name='Freezer A', storage_type='Freezer', temperature=-20)
        shelf = Shelf.objects.create(storage=storage, project=cls.project, shelf_label='Shelf A', notes='Top shelf')
        rack = Rack.objects.create(project=cls.project, project_manager=cls.root, shelf=shelf, rack_label='Rack A', capacity=10)
        box = Box.objects.create(project=cls.project, rack=rack, box_label='Box A', notes='Samples')
        sample = Sample.objects.create(project=cls.project, sample_id='SAMPLE-A', sample_type='Blood', volume=8, volume_unit='mL', collection_date=date.today())
        location = Sample_Locations.objects.create(sample=sample, box=box, well_id='A1', moved_in_at=date.today())
        consumable = Consumable.objects.create(project=cls.project, name='Pipette tips', items_per_pack=96, items_left_in_pack=50, pack_count=4, cold_storage='Room')
        cls.review_objects = [cls.project, room, storage, shelf, rack, box, sample, location, consumable, cls.department]

    def setUp(self):
        self.client.force_login(self.root)

    def test_every_registered_admin_directory_and_search_renders(self):
        from django.contrib import admin
        for model in admin.site._registry:
            url = reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
            for query in ({}, {'q': 'workspace'}):
                with self.subTest(model=model.__name__, query=query):
                    response = self.client.get(url, query)
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'admin/css/flux_admin_pages.css')
                    self.assertNotContains(response, 'Toggle theme')

    def test_every_available_admin_creation_form_renders(self):
        from django.contrib import admin
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/')
        request.user = self.root
        for model, model_admin in admin.site._registry.items():
            if model_admin.has_add_permission(request):
                with self.subTest(model=model.__name__):
                    response = self.client.get(reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_add'))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'flux-record-heading')

    def test_record_edit_history_and_deletion_review_pages_render(self):
        for obj in self.review_objects:
            for action in ('change', 'history', 'delete'):
                with self.subTest(model=obj._meta.model_name, action=action):
                    response = self.client.get(reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_{action}', args=[obj.pk]))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, 'flux_admin_pages.css')

    def test_department_rename_updates_existing_member_assignments(self):
        response = self.client.post(reverse('control:department_edit', args=[self.department.pk]), {
            'name': 'Genomics & sequencing', 'code': 'gen', 'head': self.member.pk,
            'description': 'Updated department', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.department, 'Genomics & sequencing')

    def test_inactive_department_head_can_be_preserved(self):
        self.member.is_active = False
        self.member.save()
        response = self.client.post(reverse('control:department_edit', args=[self.department.pk]), {
            'name': self.department.name, 'code': self.department.code,
            'head': self.member.pk, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.department.refresh_from_db()
        self.assertEqual(self.department.head_id, self.member.pk)

    def test_permission_picker_preserves_selected_grants_on_validation_failure(self):
        permission = Permission.objects.get(codename='view_project', content_type__app_label='inventory')
        group = Group.objects.create(name='Project reader')
        group.permissions.add(permission)
        response = self.client.get(reverse('control:role_edit', args=[group.pk]))
        self.assertContains(response, 'data-permission-section')
        self.assertRegex(response.content.decode(), rf'<input\b(?=[^>]*name="permissions")(?=[^>]*value="{permission.pk}")(?=[^>]*\bchecked)[^>]*>')
        response = self.client.post(reverse('control:role_edit', args=[group.pk]), {'name': '', 'permissions': [permission.pk]})
        self.assertRegex(response.content.decode(), rf'<input\b(?=[^>]*name="permissions")(?=[^>]*value="{permission.pk}")(?=[^>]*\bchecked)[^>]*>')
        self.assertTrue(group.permissions.filter(pk=permission.pk).exists())

    def test_role_search_and_member_counts_are_correct(self):
        group = Group.objects.create(name='Genomics reader')
        self.member.groups.add(group)
        Group.objects.create(name='Other team')
        response = self.client.get(reverse('control:roles'), {'q': 'Genomics'})
        self.assertContains(response, 'Genomics reader')
        self.assertNotContains(response, 'Other team')
        self.assertEqual(response.context['groups'][0].member_count, 1)

    def test_inventory_exports_include_only_authorized_categories(self):
        self.member.is_staff = True
        self.member.save()
        self.member.user_permissions.add(Permission.objects.get(codename='view_project', content_type__app_label='inventory'))
        self.client.force_login(self.member)
        url = reverse('control:report_csv', args=['inventory'])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.member.user_permissions.add(Permission.objects.get(codename='view_sample', content_type__app_label='inventory'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sample,1')
        self.assertNotContains(response, 'Consumable')

    def test_search_opens_the_selected_project(self):
        response = self.client.get(reverse('control:search'), {'q': 'Workspace project'})
        self.assertContains(response, reverse('admin:inventory_project_change', args=[self.project.pk]))

    @override_settings(DEBUG=False)
    def test_admin_permission_errors_use_the_shared_theme(self):
        self.member.is_staff = True
        self.member.save()
        self.client.force_login(self.member)
        response = self.client.get(reverse('admin:inventory_project_changelist'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Access is restricted.', status_code=403)
        self.assertContains(response, 'flux_admin_pages.css', status_code=403)
