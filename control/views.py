"""Integrated Django administration, backed by existing inventory and auth tables.

All state-changing endpoints are CSRF-protected POSTs, and role/permission decisions
are enforced on the server. Procurement is intentionally not simulated.
"""
import csv
from datetime import date
from functools import wraps
from urllib.parse import urlencode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from inventory.models import (Project, UserProfile, UserApplication, Consumable,
                              Reagent, Equipment, Sample, Log)
from .models import Department, AdminAudit, AdminNotification, PortalSettings
from .forms import UserForm, DepartmentForm, SettingsForm, GroupForm

User = get_user_model()


def protected(permission=None, superuser=False):
    """Gate every admin endpoint, not just its navigation entry."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f"{reverse('login')}?next={request.path}")
            if not request.user.is_active or not request.user.is_staff:
                raise PermissionDenied('Administrator access only')
            if superuser and not request.user.is_superuser:
                raise PermissionDenied('Only a super-administrator can make this change')
            if permission and not request.user.has_perm(permission):
                raise PermissionDenied('You lack this administration permission')
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def template(request, view_name, **context):
    context['section'] = view_name
    context['page_title'] = context.get('page_title', view_name.replace('_', ' ').title())
    context['unread_count'] = AdminNotification.objects.filter(recipient=request.user, read_at__isnull=True).count()
    context['portal_name'] = PortalSettings.objects.filter(pk=1).values_list('institution_name', flat=True).first() or 'Flux.Inc'
    return render(request, f'control/{view_name}.html', context)


def audit(request, action, obj, summary, changes=None):
    AdminAudit.objects.create(actor=request.user, action=action,
                              target_type=obj.__class__.__name__, target_id=str(obj.pk),
                              summary=summary[:255], changes=changes or {})


def notify_user(user, title, message, link='', event_key=''):
    data = {'title': title, 'message': message,
            'link': link if link.startswith('/control/') else ''}
    if event_key:
        AdminNotification.objects.get_or_create(recipient=user, event_key=event_key, defaults=data)
    else:
        AdminNotification.objects.create(recipient=user, **data)


def notify_staff(title, message, link='', permission=None, event_key=''):
    for recipient in User.objects.filter(is_staff=True, is_active=True):
        if recipient.is_superuser or not permission or recipient.has_perm(permission):
            notify_user(recipient, title, message, link, event_key=event_key)



def page(queryset, request, count=20):
    from django.core.paginator import Paginator
    return Paginator(queryset, count).get_page(request.GET.get('page'))


def has(request, permission):
    return request.user.has_perm(permission)


@protected()
def overview(request):
    users_visible = has(request, 'auth.view_user')
    projects_visible = has(request, 'inventory.view_project')
    stats = []
    if users_visible:
        stats.extend([
            {'title': 'Total users', 'amount': User.objects.count(), 'url': reverse('control:users'), 'icon': 'users', 'hint': 'Explore the user directory'},
            {'title': 'Active accounts', 'amount': User.objects.filter(is_active=True).count(), 'url': reverse('control:users') + '?status=active', 'icon': 'shield', 'hint': 'Accounts enabled in Flux'},
                    ])
    if has(request, 'inventory.view_userapplication'):
        stats.append({'title': 'Pending registrations', 'amount': UserApplication.objects.filter(is_approved=False).count(), 'url': reverse('admin:inventory_userapplication_changelist') + '?is_approved__exact=0', 'icon': 'clock', 'hint': 'Applications awaiting review'})
    if projects_visible:
        stats.append({'title': 'Research projects', 'amount': Project.objects.count(), 'url': reverse('admin:inventory_project_changelist'), 'icon': 'folder', 'hint': 'Explore research projects'})
    inventory_summary = []
    for model in (Consumable, Reagent, Equipment, Sample):
        if has(request, f'inventory.view_{model._meta.model_name}'):
            inventory_summary.append({'title': str(model._meta.verbose_name_plural).capitalize(),
                                      'amount': model.objects.count(),
                                      'url': reverse(f'admin:inventory_{model._meta.model_name}_changelist')})
    recent_admin = list(AdminAudit.objects.select_related('actor')[:8]) if has(request, 'control.view_adminaudit') else []
    recent_project = list(Log.objects.select_related('user', 'project')[:8]) if projects_visible else []
    projects = list(Project.objects.select_related('project_manager').prefetch_related('project_members', 'project_editors').order_by('-updated_at')[:5]) if projects_visible else []
    for project in projects:
        project.members_count = len({person.pk for person in project.project_members.all()}
                                    | {person.pk for person in project.project_editors.all()}
                                    | ({project.project_manager_id} if project.project_manager_id else set()))
    # Monthly registration trend uses only existing timestamps. No synthetic data.
    now = timezone.now()
    months = []
    if users_visible:
        for offset in range(5, -1, -1):
            year = now.year + (now.month - 1 - offset) // 12
            month = (now.month - 1 - offset) % 12 + 1
            count = User.objects.filter(date_joined__year=year, date_joined__month=month).count()
            months.append({'label': timezone.datetime(year, month, 1).strftime('%b %y'), 'value': count})
        biggest = max((item['value'] for item in months), default=0)
        for item in months:
            item['height'] = 0 if not item['value'] else max(5, round(100 * item['value'] / biggest))
    pending = list(UserApplication.objects.filter(is_approved=False).order_by('-created_at')[:5]) if has(request, 'inventory.view_userapplication') else []
    # All counts are live ORM queries, never seeded dashboard figures.
    return template(request, 'overview', page_title='Overview', stats=stats,
                    recent_admin=recent_admin, recent_project=recent_project,
                    recent_projects=projects,
                    show_users=users_visible, show_projects=projects_visible,
                    registration_months=months, pending_applications=pending,
                    inventory_summary=inventory_summary,
                    registrations_total=sum(item['value'] for item in months),
                    pending_count=next((item['amount'] for item in stats if item['icon'] == 'clock'), 0))


@protected('auth.view_user')
def users(request):
    qs = User.objects.select_related('profile').prefetch_related('groups').order_by('-date_joined')
    q = request.GET.get('q', '').strip()[:100]
    state = request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) |
                       Q(last_name__icontains=q) | Q(email__icontains=q) |
                       Q(profile__department__icontains=q)).distinct()
    if state == 'active':
        qs = qs.filter(is_active=True)
    elif state == 'inactive':
        qs = qs.filter(is_active=False)
    elif state == 'staff':
        qs = qs.filter(is_staff=True)
    return template(request, 'users', page_title='User directory', records=page(qs, request),
                    query=q, status=state, can_add=has(request, 'auth.add_user'),
                    can_edit=has(request, 'auth.change_user'))


@protected('auth.view_user')
def user_detail(request, pk):
    person = get_object_or_404(User.objects.select_related('profile').prefetch_related('groups'), pk=pk)
    managed = Project.objects.filter(project_manager=person)
    return template(request, 'user_detail', page_title='User profile', person=person, managed=managed,
                    can_edit=has(request, 'auth.change_user') and (not person.is_staff or request.user.is_superuser),
                    all_groups=Group.objects.order_by('name') if request.user.is_superuser else [])


@protected('auth.add_user')
def user_create(request):
    form = UserForm(request.POST or None, creating=True)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            person = form.save()
            audit(request, 'user.created', person, f'Account created for {person.username}')
            # Only administrators can access the control center; deliver workflow
            # notifications to eligible staff rather than a non-staff account.
            transaction.on_commit(lambda: notify_staff(
                'New account created', f'{person.username} was added to Flux.',
                reverse('control:user_detail', args=[person.pk]),
                permission='auth.view_user', event_key=f'account-created-{person.pk}'))
        messages.success(request, 'The user was created and saved successfully.')
        return redirect('control:user_detail', pk=person.pk)
    return template(request, 'user_form', page_title='Create user', form=form, editing=False)


@protected('auth.change_user')
def user_edit(request, pk):
    person = get_object_or_404(User, pk=pk)
    if person.is_staff and not request.user.is_superuser:
        raise PermissionDenied('Staff administrator account')
    form = UserForm(request.POST or None, instance=person)
    if request.method == 'POST' and form.is_valid():
        before = dict(name=person.get_full_name(), email=person.email,
                      department=UserProfile.objects.filter(user=person).values_list('department', flat=True).first())
        with transaction.atomic():
            updated = form.save()
            audit(request, 'user.updated', updated, f'Updated profile for {updated.username}',
                  {'before': before, 'after': {'name': updated.get_full_name(), 'email': updated.email,
                                               'department': form.cleaned_data.get('department', '')}})
        messages.success(request, 'Changes saved.')
        return redirect('control:user_detail', pk=person.pk)
    return template(request, 'user_form', page_title='Edit user', form=form, editing=True, person=person)


@protected('auth.change_user')
@require_POST
def user_status(request, pk):
    with transaction.atomic():
        person = get_object_or_404(User.objects.select_for_update(), pk=pk)
        if person.is_staff and not request.user.is_superuser:
            raise PermissionDenied('Cannot change a staff administrator account')
        if person.pk == request.user.pk:
            raise PermissionDenied('Cannot change your own account status')
        enable = request.POST.get('action') == 'activate'
        if request.POST.get('action') not in ('activate', 'deactivate'):
            raise PermissionDenied('Invalid action')
        if not enable and person.is_superuser:
            remaining = User.objects.filter(is_superuser=True, is_active=True).exclude(pk=person.pk).exists()
            if not remaining:
                messages.error(request, 'The only active super-administrator cannot be disabled.')
                return redirect('control:user_detail', pk=pk)
        person.is_active = enable
        person.save(update_fields=['is_active'])
        audit(request, 'user.activated' if enable else 'user.deactivated', person,
              f'{person.username} account {"activated" if enable else "deactivated"}')
    messages.success(request, 'Account status updated.')
    return redirect('control:user_detail', pk=pk)


@protected('auth.view_group')
def roles(request):
    groups = Group.objects.prefetch_related('permissions').annotate(member_count=Count('user', distinct=True)).order_by('name')
    query = request.GET.get('q', '').strip()[:100]
    if query:
        groups = groups.filter(name__icontains=query)
    return template(request, 'roles', page_title='Roles & permissions',
                    groups=groups, query=query,
                    can_manage=request.user.is_superuser)


@protected(superuser=True)
def group_form(request, pk=None):
    group = get_object_or_404(Group, pk=pk) if pk else None
    form = GroupForm(request.POST or None, instance=group)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            audit(request, 'role.updated' if pk else 'role.created', saved, f'Role permissions saved: {saved.name}',
                  {'permissions': sorted(saved.permissions.values_list('codename', flat=True))})
        messages.success(request, 'Role and permission changes saved.')
        return redirect('control:roles')
    return template(request, 'role_form', page_title='Edit role' if pk else 'Create role', form=form)


@protected(superuser=True)
@require_POST
def assign_role(request, pk):
    person = get_object_or_404(User, pk=pk)
    group = get_object_or_404(Group, pk=request.POST.get('group'))
    action = request.POST.get('action')
    if action not in ('add', 'remove'):
        raise PermissionDenied('Invalid role action')
    with transaction.atomic():
        if action == 'add':
            person.groups.add(group)
        else:
            person.groups.remove(group)
        audit(request, 'user.role', person, f'{action} role {group.name} for {person.username}')
    messages.success(request, 'Role membership updated.')
    return redirect('control:user_detail', pk=pk)


@protected('control.view_department')
def departments(request):
    qs = Department.objects.select_related('head').order_by('name')
    q = request.GET.get('q', '').strip()[:80]
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
    return template(request, 'departments', page_title='Departments & units',
                    records=page(qs, request), query=q,
                    can_edit=has(request, 'control.change_department'),
                    can_add=has(request, 'control.add_department'))


@protected()
def department_form(request, pk=None):
    perm = 'control.change_department' if pk else 'control.add_department'
    if not has(request, perm):
        raise PermissionDenied('Department editing not permitted')
    obj = get_object_or_404(Department, pk=pk) if pk else None
    old_name = obj.name if obj else None
    form = DepartmentForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = form.save()
            # Department remains a text field in original UserProfile; keep names aligned.
            if old_name and old_name != record.name:
                UserProfile.objects.filter(department=old_name).update(department=record.name)
            audit(request, 'department.updated' if pk else 'department.created', record,
                  f'Saved department {record.name}')
        messages.success(request, 'Department saved.')
        return redirect('control:departments')
    return template(request, 'department_form', page_title='Edit department' if pk else 'New department', form=form)


@protected()
def notifications(request):
    qs = AdminNotification.objects.filter(recipient=request.user)
    if request.GET.get('filter') == 'unread':
        qs = qs.filter(read_at__isnull=True)
    return template(request, 'notifications', page_title='Notification center',
                    records=page(qs, request))


@protected()
@require_POST
def notification_read(request, pk):
    AdminNotification.objects.filter(pk=pk, recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    messages.success(request, 'Notification marked as read.')
    return redirect('control:notifications')


@protected()
@require_POST
def notifications_read_all(request):
    AdminNotification.objects.filter(recipient=request.user, read_at__isnull=True).update(read_at=timezone.now())
    messages.success(request, 'All your notifications were marked as read.')
    return redirect('control:notifications')


@protected('control.view_adminaudit')
def audit_logs(request):
    qs = AdminAudit.objects.select_related('actor')
    q = request.GET.get('q', '').strip()[:100]
    if q:
        qs = qs.filter(Q(action__icontains=q) | Q(summary__icontains=q) | Q(actor__username__icontains=q))
    return template(request, 'audit_logs', page_title='Audit logs', records=page(qs, request), query=q)


@protected('control.view_portalsettings')
def portal_settings(request):
    obj = PortalSettings.objects.first() or PortalSettings(pk=1)
    can_edit = has(request, 'control.change_portalsettings')
    if request.method == 'POST' and not can_edit:
        raise PermissionDenied('Settings cannot be changed by this user')
    form = SettingsForm(request.POST or None, instance=obj)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            audit(request, 'settings.updated', obj, 'Institution settings updated',
                  {'name': obj.institution_name, 'currency': obj.currency})
        messages.success(request, 'Institution settings updated.')
        return redirect('control:settings')
    return template(request, 'settings', page_title='System settings', form=form, can_edit=can_edit)


@protected()
def profile(request):
    return template(request, 'profile', page_title='My profile', person=request.user)


def _csv_cell(value):
    """Prevent spreadsheet formulas on downloaded CSV cells."""
    cell = '' if value is None else str(value)
    if cell.lstrip().startswith(('=', '+', '-', '@', '\t', '\r')):
        return "'" + cell
    return cell


@protected()
def reports(request):
    allowed = {}
    if has(request, 'auth.view_user'):
        allowed['users'] = 'User directory'
    if has(request, 'inventory.view_project'):
        allowed['projects'] = 'Research projects'
    if any(has(request, f'inventory.view_{model._meta.model_name}') for model in (Consumable, Reagent, Equipment, Sample)):
        allowed['inventory'] = 'Inventory counts'
    if has(request, 'control.view_adminaudit'):
        allowed['audits'] = 'Administrative audit events'
    return template(request, 'reports', page_title='Reports & exports', allowed=allowed)


@protected()
def report_csv(request, report):
    permissions = {
        'users': 'auth.view_user', 'projects': 'inventory.view_project',
        'inventory': 'inventory.view_project', 'audits': 'control.view_adminaudit',
    }
    inventory_models = [model for model in (Consumable, Reagent, Equipment, Sample)
                        if has(request, f'inventory.view_{model._meta.model_name}')]
    if report not in permissions or (report == 'inventory' and not inventory_models) or (report != 'inventory' and not has(request, permissions[report])):
        raise PermissionDenied('Report access denied')
    # Validate and apply optional user-supplied reporting dates without SQL interpolation.
    try:
        date_from = date.fromisoformat(request.GET['from']) if request.GET.get('from') else None
        date_to = date.fromisoformat(request.GET['to']) if request.GET.get('to') else None
    except ValueError:
        response = template(request, 'report_error', page_title='Check report dates', error='Enter valid dates in YYYY-MM-DD format, or leave them empty to include all records.')
        response.status_code = 400
        return response
    if date_from and date_to and date_from > date_to:
        response = template(request, 'report_error', page_title='Check report dates', error='The end date must be on or after the start date.')
        response.status_code = 400
        return response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="flux-{report}.csv"'
    response.write('\ufeff')
    out = csv.writer(response)
    def write(row):
        out.writerow([_csv_cell(x) for x in row])
    if report == 'users':
        write(['Username', 'Full Name', 'Email', 'Department', 'Active', 'Staff', 'Date joined'])
        users_qs = User.objects.select_related('profile')
        if date_from:
            users_qs = users_qs.filter(date_joined__date__gte=date_from)
        if date_to:
            users_qs = users_qs.filter(date_joined__date__lte=date_to)
        for u in users_qs.iterator():
            profile = getattr(u, 'profile', None)
            write([u.username, u.get_full_name(), u.email, profile.department if profile else '',
                   u.is_active, u.is_staff, u.date_joined.isoformat()])
    elif report == 'projects':
        write(['Project', 'Principal investigator / Manager', 'Active', 'Created'])
        project_qs = Project.objects.select_related('project_manager')
        if date_from:
            project_qs = project_qs.filter(created_at__date__gte=date_from)
        if date_to:
            project_qs = project_qs.filter(created_at__date__lte=date_to)
        for p in project_qs.iterator():
            write([p.name, p.project_manager.username if p.project_manager else '',
                   p.is_active, p.created_at.isoformat()])
    elif report == 'inventory':
        write(['Inventory category', 'Total records'])
        for model in inventory_models:
            write([model.__name__, model.objects.count()])
    elif report == 'audits':
        write(['Date', 'Actor', 'Action', 'Entity', 'Entity ID', 'Summary'])
        audit_qs = AdminAudit.objects.select_related('actor')
        if date_from:
            audit_qs = audit_qs.filter(happened_at__date__gte=date_from)
        if date_to:
            audit_qs = audit_qs.filter(happened_at__date__lte=date_to)
        for a in audit_qs.iterator():
            write([a.happened_at.isoformat(), a.actor.username if a.actor else '',
                   a.action, a.target_type, a.target_id, a.summary])
    return response


@protected()
def search(request):
    q = request.GET.get('q', '').strip()[:80]
    results = []
    if q:
        if has(request, 'auth.view_user'):
            for u in User.objects.filter(Q(username__icontains=q) | Q(email__icontains=q) |
                                         Q(first_name__icontains=q) | Q(last_name__icontains=q))[:8]:
                results.append(('User', u.get_full_name() or u.username,
                                reverse('control:user_detail', args=[u.pk])))
        if has(request, 'inventory.view_project'):
            for p in Project.objects.filter(name__icontains=q)[:8]:
                results.append(('Project', p.name,
                                reverse('admin:inventory_project_change', args=[p.pk])))
        if has(request, 'control.view_department'):
            for d in Department.objects.filter(name__icontains=q)[:8]:
                results.append(('Department', d.name, reverse('control:departments') + '?' + urlencode({'q': d.name})))
    return template(request, 'search', page_title='Search', query=q, results=results)

@protected(superuser=True)
@require_POST
def user_staff_access(request, pk):
    """Only the super-administrator may grant staff portal eligibility."""
    with transaction.atomic():
        person = get_object_or_404(User.objects.select_for_update(), pk=pk)
        action = request.POST.get('action')
        if action not in ('grant', 'revoke'):
            raise PermissionDenied('Invalid access action')
        if person.is_superuser or person.pk == request.user.pk:
            raise PermissionDenied('Cannot modify super-administrator or own access')
        person.is_staff = action == 'grant'
        person.save(update_fields=['is_staff'])
        audit(request, 'user.staff_access', person, f'Administrator access {action} for {person.username}')
        notify_user(request.user, 'Administrator access updated',
                    f'You {action}ed staff administrator eligibility for {person.username}.',
                    reverse('control:user_detail', args=[person.pk]))
    messages.success(request, 'Administrator eligibility updated. Role permissions remain separately enforced.')
    return redirect('control:user_detail', pk=pk)


@protected('auth.change_user')
@require_POST
def request_password_reset(request, pk):
    """Use Django's single-use token reset flow, never expose current passwords."""
    from django.contrib.auth.forms import PasswordResetForm
    person = get_object_or_404(User, pk=pk)
    if person.is_staff and not request.user.is_superuser:
        raise PermissionDenied('Staff account recovery requires a super-administrator')
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        messages.error(request, 'Email delivery is not configured. Ask the system operator to configure FLUX_EMAIL_USER and FLUX_EMAIL_PASSWORD.')
        return redirect('control:user_detail', pk=pk)
    if not person.email or not person.is_active or not person.has_usable_password():
        messages.error(request, 'This account cannot receive a password reset link.')
        return redirect('control:user_detail', pk=pk)
    form = PasswordResetForm({'email': person.email})
    if not form.is_valid():
        messages.error(request, 'The email address could not be validated.')
        return redirect('control:user_detail', pk=pk)
    try:
        form.save(
            from_email=settings.DEFAULT_FROM_EMAIL,
            request=request,
            use_https=request.is_secure(),
            subject_template_name='control/password_reset_subject.txt',
            email_template_name='control/password_reset_email.txt',
        )
    except Exception:
        messages.error(request, 'Password recovery email delivery failed. No reset was completed.')
        return redirect('control:user_detail', pk=pk)
    audit(request, 'user.password_reset_requested', person, f'Password reset link requested for {person.username}')
    messages.success(request, 'The password reset email was sent to the account address.')
    return redirect('control:user_detail', pk=pk)


@protected(superuser=True)
def security(request):
    controls = [
        ('Debug disabled', not settings.DEBUG),
        ('Session cookies secure', settings.SESSION_COOKIE_SECURE),
        ('CSRF cookies secure', settings.CSRF_COOKIE_SECURE),
        ('HTTPS redirect active', settings.SECURE_SSL_REDIRECT),
        ('Email delivery configured', bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD)),
    ]
    return template(request, 'security', page_title='Security settings', controls=controls,
                    session_age_minutes=settings.SESSION_COOKIE_AGE // 60)
