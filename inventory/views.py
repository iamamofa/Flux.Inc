from datetime import date, datetime
import io
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from django.core.files import File
from django.core.files.uploadedfile import tempfile
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Prefetch
from django.forms import ValidationError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.crypto import hashlib
from django.db import IntegrityError
from django.views.decorators.csrf import csrf_exempt, csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

from .models import (
    UserApplication, Project, UserProfile, Log,
    Consumable, Reagent, Equipment, Sample,
    Shelf, Rack, Box, MSDSFile,
    TrashConsumable, TrashReagent, TrashEquipment, TrashSample
)
from .forms import (
    UserApplicationForm, ProjectManagerSignUpForm,
    EditorMemberSignUpForm, LoginForm
)

from .tasks import scan_file_for_viruses
from .utils.validation import handle_validation_error
from .utils.log_utils import log_performance
import csv
import json
import os
import threading
import bleach
import logging
from email.mime.image import MIMEImage
from openpyxl import Workbook
import uuid

security_logger = logging.getLogger('django.security')

static_img_path = os.path.join(settings.BASE_DIR, 'static')


# Helper functions
def get_sidebar_urls(project_name):
    return {
        'dashboard_url': reverse('dashboard_consumables',
                                 kwargs={'project_name': project_name}),
        'inventory_url': reverse('consumables',
                                 kwargs={'project_name': project_name}),
        'logs_url': reverse('log', kwargs={'project_name': project_name}),
        'trash_url': reverse('trash_reagents',
                             kwargs={'project_name': project_name}),
        'team_url': reverse('team', kwargs={'project_name': project_name}),
        'security_url': reverse('change_password'),
    }


def clean_text_field(value):
    """Sanitize text input to prevent XSS attacks"""
    if value is None:
        return ""
    # Strip harmful tags/attributes while preserving basic formatting
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'br', 'p']
    return bleach.clean(str(value), tags=allowed_tags, strip=True)


def get_user_projects(user):
    """Get all projects associated with a user"""
    try:
        user_profile = UserProfile.objects.get(user=user)
        return user_profile.managed_projects.all()
    except UserProfile.DoesNotExist:
        return Project.objects.none()


def send_email_notification(subject, template, context, recipient_list):
    """Generic email notification sender"""
    try:
        html_message = render_to_string(template, context)
        msg = EmailMultiAlternatives(
            subject,
            html_message,
            settings.EMAIL_HOST_USER,
            recipient_list
        )
        msg.mixed_subtype = 'related'
        msg.attach_alternative(html_message, "text/html")

        # Attach email images
        email_images = ["check.png", "Logo_Orange.png", "Logo_White.png",
                       "facebook2x.png", "instagram2x.png", "linkedin2x.png", "twitter2x.png"]
        for root, _, files in os.walk(f"{static_img_path}/images/"):
            for file in files:
                if file in email_images:
                    file_path = os.path.join(root, file)
                    filename = os.path.splitext(file)[0]
                    with open(file_path, 'rb') as img_file:
                        img = MIMEImage(img_file.read())
                        img.add_header('Content-Id', f'<{filename}>')
                        msg.attach(img)
        msg.send()
    except Exception as e:
        security_logger.error(f"Failed to send email: {str(e)}")


# Authentication Views
def home(request):
    """Home page view"""
    return render(request, 'inventory/home.html')


def registration_page(request):
    """Registration information page"""
    return render(request, 'inventory/registration_page.html')


@csrf_protect
def user_application(request):
    """Handle new user applications"""
    if request.method == 'POST':
        form = UserApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()

            message1 = (
                    "Your information has been submitted. Kindly be patient "
                    "as it is reviewed."
                    )
            message2 = (
                    "If you do not receive a mail in the next 24 hours, "
                    "please reach out."
                    )
            return render(
                    request,
                    'inventory/confirmed_registration.html',
                    {'message1': message1, 'message2': message2}
            )
    else:
        form = UserApplicationForm()

    return render(request, 'inventory/user_application.html', {'form': form})


def register_project_manager(request):
    """Register a new project manager"""
    email = request.GET.get('email')
    first_name = request.GET.get('first_name')
    last_name = request.GET.get('last_name')

    initial_data = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name
    } if all([email, first_name, last_name]) else None

    if request.method == 'POST':
        form = ProjectManagerSignUpForm(request.POST, request=request, initial=initial_data)
        if form.is_valid():
            try:
                project_name = form.cleaned_data['project_name']
                user = form.save()
                login(request, user, backend='inventory_system.backends.EmailBackend')

                # Create a user profile and project
                user_profile = UserProfile.objects.create(user=user)
                project = Project.objects.create(name=project_name, project_manager=user)
                user_profile.managed_projects.add(project)

                return redirect(f'/consumables/{project_name}')
            except ValidationError as e:
                form.add_error('project_name', str(e))
    else:
        form = ProjectManagerSignUpForm(request=request, initial=initial_data)

    return render(request, 'inventory/register_project_manager.html', {
        'form': form,
        'email': email,
        'first_name': first_name,
        'last_name': last_name
    })


def register_user(request):
    """Register a new editor/member user"""
    if request.method == 'POST':
        form = EditorMemberSignUpForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            login(request, user)
            UserProfile.objects.create(user=user)

            return render(request, 'inventory/user_account_created.html')
    else:
        form = EditorMemberSignUpForm(request=request)

    return render(request, 'inventory/register_user.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user)
                try:
                    user_profile = UserProfile.objects.get(user=user)
                    project = user_profile.managed_projects.first()

                    if project:
                        return redirect(f'/consumables/{project.name}')

                    message1 = "No project associated with your account."
                    message2 = "Contact your project coordinator for assistance."
                    return render(request, 'inventory/404_page.html',
                                {'message1': message1, 'message2': message2})
                except UserProfile.DoesNotExist:
                    messages.error(request, "Account not properly set up.")
            else:
                messages.error(request, 'Invalid credentials.')
    return render(request, 'inventory/login.html', {'form': LoginForm()})


@login_required
def logoutUser(request):
    """Logout the current user"""
    try:
        logout(request)
        return redirect('login')
    except Exception as e:
        security_logger.error(f"Logout error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def change_password(request):
    """Change password view"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            logout(request)
            message1 = 'Password changed successfully'
            message2 = 'Please login again with your new password'
            return render(request, 'inventory/success_page.html',
                           {'message1': message1, 'message2': message2})
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(request.user)

    projects = get_user_projects(request.user)
    project = projects.first() if projects.exists() else None

    return render(request, 'inventory/change_password.html', {
        'form': form,
        **get_sidebar_urls(project.name if project else '')
    })


# Project Team Views
@login_required
def team(request, project_name):
    """Team management view"""
    try:
        user = request.user
        project = get_object_or_404(Project, name=project_name)

        # Verify user has access to this project
        if not (project.project_manager == user or 
                project.project_editors.filter(id=user.id).exists() or 
                project.project_members.filter(id=user.id).exists()):
            return JsonResponse({'error': "Unauthorized access"}, status=403)

        team_members = (project.project_editors.all() | 
                        project.project_members.all()).distinct()

        context = {
            'project': project,
            'projects': get_user_projects(user),
            'team_members': team_members,
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/team.html', context)

    except Exception as e:
        security_logger.error(f"Team view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@ensure_csrf_cookie
def add_user_to_project(request, project_name):
    """Add user to project team"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        email = clean_text_field(request.POST.get('email'))
        role = clean_text_field(request.POST.get('role'))
        project = get_object_or_404(Project, name=project_name)
        user = get_object_or_404(User, email=email)

        # Check if user is already in project
        if (project.project_editors.filter(email=email).exists() or 
            project.project_members.filter(email=email).exists()):
            message1 = "User is already part of the project."
            message2 = "Contact support if this is an error."
            return render(request, 'inventory/404_page.html', 
                         {'message1': message1, 'message2': message2})

        # Add user based on role
        if role == 'Full':
            project.project_editors.add(user)
        elif role == 'Limited':
            project.project_members.add(user)

        # Add project to user's profile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        user_profile.managed_projects.add(project)

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Added {user.get_full_name()} to project'
        )

        return redirect(f'/team/{project_name}')

    except Exception as e:
        security_logger.error(f"Add user error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def remove_user(request, project_name, user_id):
    """Remove user from project"""
    try:
        user = get_object_or_404(User, id=user_id)
        project = get_object_or_404(Project, name=project_name)

        # Remove from both editors and members
        project.project_editors.remove(user)
        project.project_members.remove(user)

        # Remove project from user's profile
        user_profile = UserProfile.objects.get(user=user)
        user_profile.managed_projects.remove(project)

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Removed {user.get_full_name()} from project'
        )

        return JsonResponse({
            'message': f'{user.get_full_name()} removed successfully'
        }, status=200)

    except Exception as e:
        security_logger.error(f"Remove user error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def edit_user_access(request, project_name, user_id):
    """Change user's access level"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        user = get_object_or_404(User, id=user_id)
        project = get_object_or_404(Project, name=project_name)
        role = clean_text_field(request.POST.get('role'))

        if role == 'Full':
            project.project_members.remove(user)
            project.project_editors.add(user)
            action = f"Granted full access to {user.get_full_name()}"
        elif role == 'Limited':
            project.project_editors.remove(user)
            project.project_members.add(user)
            action = f"Granted limited access to {user.get_full_name()}"

        Log.objects.create(project=project, user=request.user, action=action)
        return JsonResponse({'message': "Access updated successfully"})

    except Exception as e:
        security_logger.error(f"Edit access error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Project Views
@login_required
def create_project(request):
    """Create a new project"""
    if request.method != 'POST':
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        project_name = clean_text_field(request.POST.get('project_name'))
        project = Project.objects.create(
            name=project_name,
            project_manager=request.user
        )

        # Add project to manager's profile
        user_profile = UserProfile.objects.get(user=request.user)
        user_profile.managed_projects.add(project)

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Created project {project_name}'
        )

        return JsonResponse({
            "message": "Project created successfully",
            "redirect": f"/consumables/{project_name}"
        })

    except Exception as e:
        security_logger.error(f"Create project error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Log Views
@login_required
def log(request, project_name):
    """View activity logs"""
    try:
        project = get_object_or_404(Project, name=project_name)
        logs = Log.objects.filter(project=project).order_by('-timestamp')

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'logs': logs,
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/logs.html', context)

    except Exception as e:
        security_logger.error(f"Log view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Base Inventory Views
class InventoryItemViews:
    """Base class for inventory item views"""

    @classmethod
    def list_view(cls, request, project_name, template_name, model, count_attr):
        """Generic list view for inventory items"""
        try:
            project = get_object_or_404(Project, name=project_name)
            items = model.objects.filter(project__name=project_name)

            # Pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(items, 50)
            try:
                items_page = paginator.page(page)
            except PageNotAnInteger:
                items_page = paginator.page(1)
            except EmptyPage:
                items_page = paginator.page(paginator.num_pages)

            if count_attr:
                context = {
                    'project': project,
                    'projects': get_user_projects(request.user),
                    template_name: items,
                    'user': request.user,
                    'total_count': model.objects.get_project_stats(project_name)['total_count'],
                    'expiring_soon_count': model.objects.get_project_stats(project_name)['expiring_soon_count'],
                    'low_stock_count': model.objects.get_project_stats(project_name)['low_stock_count'],
                    'page_obj': items_page,
                    **get_sidebar_urls(project_name)
                }
            else:
                context = {
                    'project': project,
                    'projects': get_user_projects(request.user),
                    template_name: items,
                    'user': request.user,
                    'page_obj': items_page,
                    **get_sidebar_urls(project_name)
                }

            return render(request, f'inventory/{template_name}.html', context)

        except Exception as e:
            security_logger.error(f"{template_name} list view error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def dashboard_view(cls, request, project_name, template_name, model, value_field):
        """Generic dashboard view"""
        try:
            project = get_object_or_404(Project, name=project_name)
            items = model.objects.filter(project=project, is_active=True)

            # Prepare chart data
            names = [item.name for item in items]
            values = [getattr(item, value_field) for item in items]
            plot_data = json.dumps({'names': names, 'values': values})

            context = {
                'plot_data': plot_data,
                'project': project,
                'projects': get_user_projects(request.user),
                'items': items,
                **get_sidebar_urls(project_name)
            }
            return render(request, f'inventory/{template_name}.html', context)

        except Exception as e:
            security_logger.error(f"{template_name} dashboard error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def add_item(cls, request, project_name, model, fields, success_message):
        """Generic add item view"""
        if request.method != 'POST':
            return JsonResponse({'error': 'Invalid request method'}, status=405)

        try:
            project = get_object_or_404(Project, name=project_name)
            data = {}

            for field, field_type in fields.items():
                value = request.POST.get(field, '')
                if field_type == 'int':
                    data[field] = int(value) if value else 0
                elif field_type == 'bool':
                    data[field] = value
                elif field_type == 'date':
                    if value:
                        data[field] = datetime.strptime(value, '%Y-%m-%d').date()
                        if data[field] < date.today():
                            return JsonResponse({'error': 'Date cannot be in past'}, status=400)
                else:
                    data[field] = clean_text_field(value)

            # Create the item
            item = model.objects.create(
                    project=project,
                    items_left_in_pack=data['items_per_pack'],
                    **data
            )

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Added {data.get("name", "item")} to {model.__name__}'
            )

            return JsonResponse({
                'success': True,
                'refresh': True,
                'id': item.id,
                'name': getattr(item, 'name', ''),
                'message': success_message
            })

        except ValidationError as e:
            errors = handle_validation_error(e)
            return JsonResponse({'errors': errors}, status=400)
        except ValueError as e:
            security_logger.error(f"Add item validation error: {str(e)}")
            return JsonResponse({'error': f'Invalid input: {str(e)}'}, status=400)
        except Exception as e:
            security_logger.error(f"Add item error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def edit_item(cls, request, item_id, model, fields):
        """Generic edit item view"""
        if request.method != 'POST':
            return JsonResponse({'error': "Invalid request method"}, status=405)

        try:
            item = get_object_or_404(model, id=item_id)
            old_values = {field: getattr(item, field) for field in fields.keys()}
            new_values = {}
            changed_fields = []

            for field, field_type in fields.items():
                value = request.POST.get(field, getattr(item, field))
                if field_type == 'int':
                    new_values[field] = int(value) if value else 0
                elif field_type == 'bool':
                    new_values[field] = value
                elif field_type == 'date':
                    new_values[field] = datetime.strptime(value, '%Y-%m-%d').date() if value else None
                else:
                    new_values[field] = clean_text_field(value)

                if str(old_values[field]) != str(new_values[field]):
                    changed_fields.append(f"{field} (from '{old_values[field]}' to '{new_values[field]}')")

            # Update the item
            for field, value in new_values.items():
                setattr(item, field, value)
            item.save()

            # Log changes
            if changed_fields:
                action = f"{getattr(item, 'name', 'Item')} updated: " + ", ".join(changed_fields)
            else:
                action = f"{getattr(item, 'name', 'Item')} details viewed (no changes)"

            Log.objects.create(
                project=item.project,
                user=request.user,
                action=action
            )

            return JsonResponse({
                'success': True,
                'refresh': bool(changed_fields),
                'id': item.id,
                **{field: new_values[field] for field in fields.keys()}
            })

        except Exception as e:
            security_logger.error(f"Edit item error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def delete_item(cls, request, project_name, item_id, model, trash_model):
        """Generic delete item view (move to trash)"""
        try:
            project = get_object_or_404(Project, name=project_name)
            item = get_object_or_404(model, id=item_id, project=project)

            # Create trash record
            trash_data = {field.name: getattr(item, field.name) 
                         for field in item._meta.fields 
                         if field.name not in ['id', 'project']}
            trash_model.objects.create(project=project, **trash_data)

            # Delete original
            item_name = getattr(item, 'name', str(item))
            item.delete()

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Moved {item_name} to trash'
            )

            return JsonResponse({
                'success': True,
                'refresh': True,
                'message': f'{item_name} moved to trash'
            }, status=200)

        except Exception as e:
            security_logger.error(f"Delete item error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def restore_item(cls, request, project_name, trash_id, model, trash_model):
        """Generic restore item from trash"""
        try:
            project = get_object_or_404(Project, name=project_name)
            trash_item = get_object_or_404(trash_model, id=trash_id, project=project)

            # Create new item from trash data
            item_data = {field.name: getattr(trash_item, field.name) 
                        for field in trash_item._meta.fields 
                        if field.name not in ['id', 'project', 'deleted_at', 'deleted_by', 'deletion_reason']}
            item = model.objects.create(project=project, **item_data)

            # Delete trash record
            trash_item.delete()

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Restored {getattr(item, "name", "item")} from trash'
            )

            return JsonResponse({
                'success': True,
                'refresh': True,
                'message': f'{getattr(item, "name", "item")} restored'
            })

        except Exception as e:
            security_logger.error(f"Restore item error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def permanent_delete(cls, request, trash_id, trash_model):
        """Generic permanent delete from trash"""
        try:
            trash_item = get_object_or_404(trash_model, id=trash_id)
            trash_item.delete()

            Log.objects.create(
                project=trash_item.project,
                user=request.user,
                action=f'Permanently deleted {getattr(trash_item, "name", "item")} from trash'
            )

            return JsonResponse({
                'success': True,
                'refresh': True,
                'message': 'Item permanently deleted'
            })

        except Exception as e:
            security_logger.error(f"Permanent delete error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def empty_trash(cls, request, project_name, trash_model):
        """Generic empty trash view"""
        try:
            project = get_object_or_404(Project, name=project_name)
            count, _ = trash_model.objects.filter(project=project).delete()

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Emptied trash ({count} items)'
            )

            return JsonResponse({
                'success': True,
                'refresh': True,
                'message': f'Deleted {count} items from trash'
            })

        except Exception as e:
            security_logger.error(f"Empty trash error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def export_csv(cls, request, project_name, model, fields, filename):
        """Generic CSV export"""
        try:
            project = get_object_or_404(Project, name=project_name)
            items = model.objects.filter(project=project, is_active=True)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'

            writer = csv.writer(response)
            writer.writerow(fields.keys())

            for item in items:
                writer.writerow([getattr(item, field) for field in fields.keys()])

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Exported {model.__name__} to CSV'
            )

            return response

        except Exception as e:
            security_logger.error(f"CSV export error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def export_excel(cls, request, project_name, model, fields, filename):
        """Generic Excel export"""
        try:
            project = get_object_or_404(Project, name=project_name)
            items = model.objects.filter(project=project, is_active=True)

            workbook = Workbook()
            sheet = workbook.active
            sheet.append(list(fields.keys()))

            for item in items:
                sheet.append([getattr(item, field) for field in fields.keys()])

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
            workbook.save(response)

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Exported {model.__name__} to Excel'
            )

            return response

        except Exception as e:
            security_logger.error(f"Excel export error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)

    @classmethod
    def export_txt(cls, request, project_name, model, fields, filename):
        """Generic text export"""
        try:
            project = get_object_or_404(Project, name=project_name)
            items = model.objects.filter(project=project, is_active=True)

            response = HttpResponse(content_type='text/plain')
            response['Content-Disposition'] = f'attachment; filename="{filename}.txt"'

            lines = []
            for item in items:
                item_lines = [f"{label}: {getattr(item, field)}" 
                            for field, label in fields.items()]
                lines.extend(item_lines)
                lines.append("")  # Add empty line between items

            response.write('\n'.join(lines))

            Log.objects.create(
                project=project,
                user=request.user,
                action=f'Exported {model.__name__} to text'
            )

            return response

        except Exception as e:
            security_logger.error(f"Text export error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)


# Consumable Views
@login_required
def consumables(request, project_name):
    """List consumables view"""
    return InventoryItemViews.list_view(
        request, project_name, 'consumables', Consumable, count_attr=True
    )


@login_required
def dashboard_consumables(request, project_name):
    """Consumables dashboard view"""
    return InventoryItemViews.dashboard_view(
        request, project_name, 'dashboard_consumables', Consumable, 'items_left_in_pack'
    )


@login_required
@ensure_csrf_cookie
def add_consumable(request, project_name):
    """Add new consumable"""
    fields = {
        'name': 'text',
        'product_code': 'text',
        'items_per_pack': 'int',
        'pack_count': 'int',
        'expiry_date': 'date',
        'storage_location': 'text',
        'cold_storage': 'text',
        'oem_temperature': 'int',
        'temperature_unit': 'text',
        'vendor': 'text',
        'threshold_value': 'int',
        'notes': 'text'
    }
    return InventoryItemViews.add_item(
        request, project_name, Consumable, fields, 'Consumable added successfully'
    )


@login_required
@ensure_csrf_cookie
def edit_consumable(request, consumable_id):
    """Edit consumable"""
    fields = {
        'name': 'text',
        'product_code': 'text',
        'items_per_pack': 'int',
        'pack_count': 'int',
        'expiry_date': 'date',
        'storage_location': 'text',
        'cold_storage': 'text',
        'oem_temperature': 'int',
        'vendor': 'text',
        'threshold_value': 'int',
        'notes': 'text'
    }
    return InventoryItemViews.edit_item(request, consumable_id, Consumable, fields)


@login_required
def delete_consumable(request, project_name, consumable_id):
    """Move consumable to trash"""
    return InventoryItemViews.delete_item(
        request, project_name, consumable_id, Consumable, TrashConsumable
    )


@login_required
def trash_consumables(request, project_name):
    """View trashed consumables"""
    try:
        project = get_object_or_404(Project, name=project_name)
        trash_items = TrashConsumable.objects.filter(project=project)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'trash_items': trash_items,
            'item_type': 'consumables',
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/trash_consumables.html', context)

    except Exception as e:
        security_logger.error(f"Trash consumables view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def restore_consumable(request, project_name, trash_id):
    """Restore consumable from trash"""
    return InventoryItemViews.restore_item(
        request, project_name, trash_id, Consumable, TrashConsumable
    )


@login_required
def delete_trash_consumable(request, trash_id):
    """Permanently delete consumable from trash"""
    return InventoryItemViews.permanent_delete(request, trash_id, TrashConsumable)


@login_required
def empty_consumable_trash(request, project_name):
    """Empty consumable trash"""
    return InventoryItemViews.empty_trash(request, project_name, TrashConsumable)


@login_required
@ensure_csrf_cookie
def retrieve_consumable(request, consumable_id):
    """Retrieve/use consumable items"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        consumable = get_object_or_404(Consumable, id=consumable_id)
        option = clean_text_field(request.POST.get('retrieve_by', ''))
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)

        if option == 'Pack size':
            # Handle partial pack retrieval logic
            tmp = consumable.items_left_in_pack - amount

            if tmp == 0:
                consumable.pack_count -= 1
                consumable.items_left_in_pack = consumable.items_per_pack
                log_msg = f"1 pack of {consumable.name} consumed"
            elif tmp > 0:
                consumable.items_left_in_pack = tmp
                log_msg = f"{amount} items removed from open pack of {consumable.name}"
            else:
                full_packs_used = abs(tmp) // consumable.items_per_pack
                remainder = abs(tmp) % consumable.items_per_pack

                consumable.pack_count -= (full_packs_used + 1)
                consumable.items_left_in_pack = (
                    consumable.items_per_pack if remainder == 0 
                    else consumable.items_per_pack - remainder
                )
                log_msg = (
                    f"{amount} items removed from {consumable.name} - "
                    f"{full_packs_used + 1} packs consumed"
                )
        else:
            # Handle full pack retrieval
            consumable.pack_count -= amount
            log_msg = f"{amount} full pack(s) of {consumable.name} consumed"

        consumable.save()

        # Check threshold and send notification if needed
        if consumable.pack_count < consumable.threshold_value:
            threading.Thread(
                target=send_email_notification,
                args=(
                    f"Consumable {consumable.name} below threshold",
                    'inventory/shortage_email_template.html',
                    {'item': consumable, 'type': 'consumable'},
                    [consumable.project.project_manager.email]
                )
            ).start()

        Log.objects.create(
            project=consumable.project,
            user=request.user,
            action=log_msg
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': consumable.id,
            'name': consumable.name,
            'product_code': consumable.product_code,
            'pack_count': consumable.pack_count,
            'items_left_in_pack': consumable.items_left_in_pack,
            'items_per_pack': consumable.items_per_pack,
            'date_recorded': consumable.date_recorded,
            'expiry_date': consumable.expiry_date,
            'storage_location': consumable.storage_location,
            'threshold_value': consumable.threshold_value,
            'cold_storage': consumable.cold_storage,
            'vendor': consumable.vendor,
            'notes': consumable.notes,
            'is_active': consumable.is_active,
            'oem_temperature': consumable.oem_temperature
        })

    except Exception as e:
        security_logger.error(f"Retrieve consumable error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def restock_consumable(request, consumable_id):
    """Restock consumable items to inventory"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        consumable = get_object_or_404(Consumable, id=consumable_id)
        option = clean_text_field(request.POST.get('restock_by', ''))
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)

        if option == 'Pack size':
            # Handle partial pack return logic
            tmp = consumable.items_left_in_pack + amount

            if tmp <= consumable.items_per_pack:
                consumable.items_left_in_pack = tmp
                log_msg = f"{amount} items returned to open pack of {consumable.name}"
            else:
                full_packs_added = tmp // consumable.items_per_pack
                remainder = tmp % consumable.items_per_pack

                consumable.pack_count += full_packs_added
                consumable.items_left_in_pack = (
                    consumable.items_per_pack if remainder == 0 
                    else remainder
                )
                log_msg = (
                    f"{full_packs_added} pack(s) and {remainder} items "
                    f"returned to {consumable.name} stock"
                )
        else:
            # Handle full pack return
            consumable.pack_count += amount
            log_msg = f"{amount} full pack(s) of {consumable.name} returned"

        consumable.save()

        Log.objects.create(
            project=consumable.project,
            user=request.user,
            action=log_msg
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': consumable.id,
            'name': consumable.name,
            'product_code': consumable.product_code,
            'date_recorded': consumable.date_recorded,
            'expiry_date': consumable.expiry_date,
            'storage_location': consumable.storage_location,
            'threshold_value': consumable.threshold_value,
            'pack_count': consumable.pack_count,
            'items_left_in_pack': consumable.items_left_in_pack,
            'items_per_pack': consumable.items_per_pack,
            'cold_storage': consumable.cold_storage,
            'vendor': consumable.vendor,
            'notes': consumable.notes,
            'is_active': consumable.is_active,
            'oem_temperature': consumable.oem_temperature
        })

    except Exception as e:
        security_logger.error(f"Return consumable error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_consumable_csv(request, project_name):
    """Export consumables to CSV"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'cold_storage': 'Cold Storage',
        'notes': 'Notes',
        'is_active': 'Is Active',
    }
    return InventoryItemViews.export_csv(
        request, project_name, Consumable, fields, 'consumables'
    )


@login_required
def export_consumable_excel(request, project_name):
    """Export consumables to Excel"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'cold_storage': 'Cold Storage',
        'notes': 'Notes',
        'is_active': 'Is Active',
    }
    return InventoryItemViews.export_excel(
        request, project_name, Consumable, fields, 'consumables'
    )


@login_required
def export_consumable_txt(request, project_name):
    """Export consumables to text"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'cold_storage': 'Cold Storage',
        'notes': 'Notes',
        'is_active': 'Is Active',
    }
    return InventoryItemViews.export_txt(
        request, project_name, Consumable, fields, 'consumables'
    )


@login_required
def get_consumable_info(request, id):
    """Get the info of a consumable"""
    try:
        consumable = Consumable.objects.get(id=id)

        # Prepare the data to be sent back as a JSON response
        data = {
            'name': clean_text_field(consumable.name),
            'product_code': clean_text_field(consumable.product_code),
            'items_per_pack': consumable.items_per_pack,
            'items_left_in_pack': consumable.items_left_in_pack,
            'pack_count': consumable.pack_count,
            'expiry_date': consumable.expiry_date.strftime('%Y-%m-%d') if consumable.expiry_date else '',
            'date_recorded': consumable.date_recorded.strftime('%Y-%m-%d') if consumable.date_recorded else '',
            'cold_storage': consumable.cold_storage,
            'storage_location': clean_text_field(consumable.storage_location),
            'threshold_value': consumable.threshold_value,
            'vendor': consumable.vendor,
            'notes': consumable.notes,
            'is_active': consumable.is_active,
            'oem_temperature': consumable.oem_temperature
        }

        return JsonResponse(data)

    except Exception as e:
        security_logger.error(f"Get consumable info error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


# Reagent Views
@login_required
def reagents(request, project_name):
    """List reagents view with performance optimizations"""
    try:
        project = get_object_or_404(Project, name=project_name)

        # Optimized query with select_related and prefetch_related
        reagents = Reagent.objects.filter(
            project=project,
            is_active=True
        ).select_related('project').prefetch_related(
            Prefetch('msds_files',
                    queryset=MSDSFile.objects.all().only(
                        'id', 'original_filename', 'upload_date', 'scan_result'
                    ).order_by('-upload_date'),
                    to_attr='latest_msds')
        ).only(
            'id', 'name', 'product_code', 'items_per_pack',
            'items_left_in_pack', 'pack_count', 'expiry_date',
            'date_recorded', 'storage_location', 'cold_storage',
            'oem_temperature', 'temperature_unit', 'vendor',
            'country_of_origin', 'hazard_level', 'threshold_value', 'notes'
        )

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(reagents, 50)  # 50 items per page
        try:
            reagents_page = paginator.page(page)
        except PageNotAnInteger:
            reagents_page = paginator.page(1)
        except EmptyPage:
            reagents_page = paginator.page(paginator.num_pages)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'reagents': reagents_page,
            'user': request.user,
            'total_count': Reagent.objects.get_project_stats(project_name)['total_count'],
            'expiring_soon_count': Reagent.objects.get_project_stats(project_name)['expiring_soon_count'],
            'low_stock_count': Reagent.objects.get_project_stats(project_name)['low_stock_count'],
            'page_obj': reagents_page,
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/reagents.html', context)

    except Exception as e:
        security_logger.error(f"Reagents view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def dashboard_reagents(request, project_name):
    return InventoryItemViews.dashboard_view(
        request, project_name, 'dashboard_reagents', Reagent, 'items_left_in_pack'
    )


@login_required
@ensure_csrf_cookie
def add_reagent(request, project_name):
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        project = Project.objects.get(name=project_name)

        # Handle storage condition
        storage_condition = request.POST.get('storage_condition', '')
        if storage_condition == 'other':
            storage_condition = request.POST.get('storage_condition_other', '')

        temperature_unit = request.POST.get('temperature_unit', 'C')

        expiry_date_str = request.POST.get('expiry_date')
        expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date() if expiry_date_str else None

        if expiry_date < date.today():
            return JsonResponse({
                'error': 'Expiry date cannot be in the past.'
            }, status=400)

        data = {
            'name': clean_text_field(request.POST.get('name', '')),
            'product_code': clean_text_field(request.POST.get('product_code', '')),
            'items_per_pack': int(request.POST.get('items_per_pack', 0)),
            'pack_count': int(request.POST.get('pack_count', 0)),
            'expiry_date': expiry_date,
            'storage_location': clean_text_field(request.POST.get('storage_location', '')),
            'cold_storage': storage_condition,
            'oem_temperature': int(request.POST.get('oem_temperature', 0)),
            'temperature_unit': temperature_unit,
            'vendor': clean_text_field(request.POST.get('vendor', '')),
            'country_of_origin': clean_text_field(request.POST.get('country_of_origin', '')),
            'hazard_level': int(request.POST.get('hazard_level', 0)),
            'threshold_value': int(request.POST.get('threshold_value', 0)),
            'notes': clean_text_field(request.POST.get('notes', ''))
        }

        # Create a new Reagent instance associated with the active project
        reagent = Reagent(
                project=project,
                items_left_in_pack=data['items_per_pack'],
                **data
        )

        # Validate then save new Reagent instance
        reagent.full_clean()
        reagent.save()

        # Handle MSDS file if included
        if 'msds_file' in request.FILES:
            handle_msds_upload(request.FILES['msds_file'], reagent, request.user)

        Log.objects.create(
                project=project,
                user=request.user,
                action=f'{data["name"]} added to Reagents'
        )

        return JsonResponse({
                'success': True,
                'refresh': True,
                'id': reagent.id,
                'name': reagent.name,
                'has_msds': reagent.msds_files.exists(),
                'msds': get_latest_msds_data(reagent) if reagent.msds_files.exists() else None,
                'message': f'{data["name"]} added to Reagents'
        })

    except ValidationError as e:
        errors = handle_validation_error(e)
        return JsonResponse({'errors': errors}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@login_required
@ensure_csrf_cookie
def edit_reagent(request, reagent_id):
    """Edit reagent"""
    fields = {
        'name': 'text',
        'product_code': 'text',
        'items_per_pack': 'int',
        'items_left_in_pack': 'int',
        'pack_count': 'int',
        'expiry_date': 'date',
        'storage_location': 'text',
        'cold_storage': 'text',
        'oem_temperature': 'int',
        'vendor': 'text',
        'country_of_origin': 'text',
        'hazard_level': 'int',
        'threshold_value': 'int',
        'notes': 'text'
    }

    return InventoryItemViews.edit_item(request, reagent_id, Reagent, fields)


def get_latest_msds_data(reagent):
    msds = reagent.msds_files.latest('upload_date')
    return {
        'id': msds.id,
        'filename': msds.original_filename,
        'uploaded_by': msds.uploaded_by,
        'upload_date': msds.upload_date.strftime('%Y-%m-%d'),
        'scan_result': msds.scan_result,
        'download_url': reverse('download_msds', args=[msds.id])
    }


@login_required
def delete_reagent(request, project_name, reagent_id):
    """Move reagent to trash"""
    return InventoryItemViews.delete_item(
        request, project_name, reagent_id, Reagent, TrashReagent
    )


@login_required
def trash_reagents(request, project_name):
    """View trashed reagents"""
    try:
        project = get_object_or_404(Project, name=project_name)
        trash_items = TrashReagent.objects.filter(project=project)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'trash_items': trash_items,
            'item_type': 'reagents',
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/trash_reagents.html', context)

    except Exception as e:
        security_logger.error(f"Trash reagents view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def restore_reagent(request, project_name, trash_id):
    """Restore reagent from trash"""
    return InventoryItemViews.restore_item(
        request, project_name, trash_id, Reagent, TrashReagent
    )


@login_required
def delete_trash_reagent(request, trash_id):
    """Permanently delete reagent from trash"""
    return InventoryItemViews.permanent_delete(request, trash_id, TrashReagent)


@login_required
def empty_reagent_trash(request, project_name):
    """Empty reagent trash"""
    return InventoryItemViews.empty_trash(request, project_name, TrashReagent)


@login_required
@ensure_csrf_cookie
def retrieve_reagent(request, reagent_id):
    """Retrieve/use reagent items"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        reagent = get_object_or_404(Reagent, id=reagent_id)
        option = clean_text_field(request.POST.get('retrieve_by', ''))
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)

        if option == 'Pack size':
            # Handle partial pack retrieval logic
            tmp = reagent.items_left_in_pack - amount

            if tmp == 0:
                reagent.pack_count -= 1
                reagent.items_left_in_pack = reagent.items_per_pack
                log_msg = f"1 pack of {reagent.name} consumed"
            elif tmp > 0:
                reagent.items_left_in_pack = tmp
                log_msg = f"{amount} items removed from open pack of {reagent.name}"
            else:
                full_packs_used = abs(tmp) // reagent.items_per_pack
                remainder = abs(tmp) % reagent.items_per_pack

                reagent.pack_count -= (full_packs_used + 1)
                reagent.items_left_in_pack = (
                    reagent.items_per_pack if remainder == 0 
                    else reagent.items_per_pack - remainder
                )
                log_msg = (
                    f"{amount} items removed from {reagent.name} - "
                    f"{full_packs_used + 1} packs consumed"
                )
        else:
            # Handle full pack retrieval
            reagent.pack_count -= amount
            log_msg = f"{amount} full pack(s) of {reagent.name} consumed"

        reagent.save()

        # Check threshold and send notification if needed
        if reagent.pack_count < reagent.threshold_value:
            threading.Thread(
                target=send_email_notification,
                args=(
                    f"Reagent {reagent.name} below threshold",
                    'inventory/shortage_email_template.html',
                    {'item': reagent, 'type': 'reagent'},
                    [reagent.project.project_manager.email]
                )
            ).start()

        Log.objects.create(
            project=reagent.project,
            user=request.user,
            action=log_msg
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': reagent.id,
            'name': reagent.name,
            'product_code': reagent.product_code,
            'items_per_pack': reagent.items_per_pack,
            'items_left_in_pack': reagent.items_left_in_pack,
            'pack_count': reagent.pack_count,
            'date_recorded': reagent.date_recorded,
            'expiry_date': reagent.expiry_date,
            'storage_location': reagent.storage_location,
            'threshold_value': reagent.threshold_value,
            'oem_temperature': reagent.oem_temperature,
            'temperature_unit': reagent.temperature_unit,
            'country_of_origin': reagent.country_of_origin,
            'hazard_level': reagent.hazard_level
        })

    except Exception as e:
        security_logger.error(f"Retrieve reagent error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def restock_reagent(request, reagent_id):
    """Return reagent items to inventory"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        reagent = get_object_or_404(Reagent, id=reagent_id)
        option = clean_text_field(request.POST.get('return_by', ''))
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)

        if option == 'Pack size':
            # Handle partial pack return logic
            tmp = reagent.items_left_in_pack + amount

            if tmp <= reagent.items_per_pack:
                reagent.items_left_in_pack = tmp
                log_msg = f"{amount} items returned to open pack of {reagent.name}"
            else:
                full_packs_added = tmp // reagent.items_per_pack
                remainder = tmp % reagent.items_per_pack

                reagent.pack_count += full_packs_added
                reagent.items_left_in_pack = (
                    reagent.items_per_pack if remainder == 0
                    else remainder
                )
                log_msg = (
                    f"{full_packs_added} pack(s) and {remainder} items "
                    f"returned to {reagent.name} stock"
                )
        else:
            # Handle full pack return
            reagent.pack_count += amount
            log_msg = f"{amount} full pack(s) of {reagent.name} returned"

        reagent.save()

        Log.objects.create(
            project=reagent.project,
            user=request.user,
            action=log_msg
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': reagent.id,
            'name': reagent.name,
            'product_code': reagent.product_code,
            'items_per_pack': reagent.items_per_pack,
            'items_left_in_pack': reagent.items_left_in_pack,
            'pack_count': reagent.pack_count,
            'date_recorded': reagent.date_recorded,
            'expiry_date': reagent.expiry_date,
            'storage_location': reagent.storage_location,
            'threshold_value': reagent.threshold_value,
            'oem_temperature': reagent.oem_temperature,
            'temperature_unit': reagent.temperature_unit,
            'country_of_origin': reagent.country_of_origin,
            'hazard_level': reagent.hazard_level
        })

    except Exception as e:
        security_logger.error(f"Return reagent error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_reagent_csv(request, project_name):
    """Export reagents to CSV"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'temperature_unit': 'Temperature Unit',
        'country_of_origin': 'Country of Origin',
        'hazard_level': 'Hazard Level'
    }
    return InventoryItemViews.export_csv(
        request, project_name, Reagent, fields, 'reagents'
    )


@login_required
def export_reagent_excel(request, project_name):
    """Export reagents to Excel"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'temperature_unit': 'Temperature Unit',
        'country_of_origin': 'Country of Origin',
        'hazard_level': 'Hazard Level'
    }
    return InventoryItemViews.export_excel(
        request, project_name, Reagent, fields, 'reagents'
    )


@login_required
def export_reagent_txt(request, project_name):
    """Export reagents to text"""
    fields = {
        'name': 'Name',
        'product_code': 'Product Code',
        'items_per_pack': 'Items per Pack',
        'items_left_in_pack': 'Items Left',
        'pack_count': 'Pack Count',
        'expiry_date': 'Expiry Date',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'date_recorded': 'Date Recorded',
        'oem_temperature': 'Manufacturer Recommended Temperature',
        'temperature_unit': 'Temperature Unit',
        'country_of_origin': 'Country of Origin',
        'hazard_level': 'Hazard Level'
    }
    return InventoryItemViews.export_txt(
        request, project_name, Reagent, fields, 'reagents'
    )


@login_required
def get_reagent_info(request, id):
    """Get the info of a reagent"""
    try:
        reagent = Reagent.objects.get(id=id)

        # Verify user has access to this reagent's project
        if not (request.user == reagent.project.project_manager or 
                request.user in reagent.project.project_editors.all() or
                request.user in reagent.project.project_members.all()):
            return JsonResponse({'error': 'Unauthorized access'}, status=403)

        # Get MSDS info if exists
        msds_data = None
        if reagent.msds_files.exists():
            lastest_msds = reagent.msds_files.latest('upload_date')
            msds_data = {
                    'id': lastest_msds.id,
                    'filename': lastest_msds.original_filename,
                    'upload_date': lastest_msds.upload_date.strftime('%Y-%m-%d'),
                    'scan_result': lastest_msds.scan_result,
                    'download_url': reverse('download_msds', kwargs={'msds_id': lastest_msds.id}),
                    'verified': lastest_msds.is_verified
            }

        # Prepare the data to be sent back as a JSON response
        data = {
            'id': reagent.id,
            'name': clean_text_field(reagent.name),
            'product_code': clean_text_field(reagent.product_code),
            'items_per_pack': reagent.items_per_pack,
            'items_left_in_pack': reagent.items_left_in_pack,
            'pack_count': reagent.pack_count,
            'expiry_date': reagent.expiry_date.strftime('%Y-%m-%d') if reagent.expiry_date else None,
            'date_recorded': reagent.date_recorded.strftime('%Y-%m-%d'),
            'storage_location': clean_text_field(reagent.storage_location),
            'threshold_value': reagent.threshold_value,
            'oem_temperature': reagent.oem_temperature,
            'temperature_unit': reagent.temperature_unit,
            'country_of_origin': reagent.country_of_origin,
            'hazard_level': reagent.hazard_level,
            'has_msds': reagent.msds_files.exists(),
            'current_msds': msds_data
        }

        return JsonResponse(data)

    except Reagent.DoesNotExist:
        return JsonResponse({'error': "Reagent not found"}, status=404)
    except Exception as e:
        security_logger.error(f"Get reagent info error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)


# Equipment Views
@login_required
def equipment_(request, project_name):
    return InventoryItemViews.list_view(
        request, project_name, 'equipment', Equipment, TrashEquipment
    )


@login_required
def dashboard_equipment_(request, project_name):
    return InventoryItemViews.dashboard_view(
        request, project_name, 'dashboard_equipment', Equipment, 'quantity'
    )


@login_required
@ensure_csrf_cookie
def add_equipment_(request, project_name):
    fields = {
        'name': 'text',
        'equip_id': 'text',
        'serial_num': 'text',
        'status': 'text',
        'service_contract_start': 'date',
        'service_contract_end': 'date',
        'source': 'text',
        'operating_temperature': 'int',
        'storage_location': 'text',
        'warranty_end_date': 'date',
        'last_calibration_date': 'date',
        'next_calibration_date': 'date',
        'notes': 'text',
        'is_active': 'bool',
        'created_at': 'date',
        'updated_at': 'date'
    }
    return InventoryItemViews.add_item(
        request, project_name, Equipment, fields, 'Equipment added successfully'
    )


@login_required
@ensure_csrf_cookie
def edit_equipment_(request, equipment_id):
    """Edit equipment with fault notification handling"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        equipment = get_object_or_404(Equipment, id=equipment_id)
        old_status = equipment.status
        old_values = {
            'name': equipment.name,
            'equip_id': equipment.equip_id,
            'serial_num': equipment.serial_num,
            'quantity': equipment.quantity,
            'status': old_status,
            'service_contract_start': equipment.service_contract_start,
            'service_contract_end': equipment.service_contract_end,
            'source': equipment.source,
            'storage_location': equipment.storage_location
        }

        # Get new values from request
        new_values = {
            field: request.POST.get(field, getattr(equipment, field))
            for field in old_values.keys()
        }
        new_values['quantity'] = int(new_values['quantity'])

        # Check for status change to faulty
        new_status = new_values['status']
        status_changed_to_faulty = (new_status == "Faulty" and old_status != "Faulty")

        # Update the equipment
        for field, value in new_values.items():
            setattr(equipment, field, value)
        equipment.save()

        # Send fault notification if needed
        if status_changed_to_faulty:
            threading.Thread(
                target=send_equipment_fault_notification,
                args=(equipment,)
            ).start()

        # Log changes
        changed_fields = [
            f"{field} (from '{old_values[field]}' to '{new_values[field]}')"
            for field in old_values if str(old_values[field]) != str(new_values[field])
        ]

        action = (f"{equipment.name} marked as faulty" if status_changed_to_faulty
                 else f"{equipment.name} updated: " + ", ".join(changed_fields) if changed_fields
                 else f"{equipment.name} details viewed (no changes)")

        Log.objects.create(
            project=equipment.project,
            user=request.user,
            action=action
        )

        return JsonResponse({
            'success': True,
            'refresh': bool(changed_fields),
            'id': equipment.id,
            **new_values
        })

    except Exception as e:
        security_logger.error(f"Edit equipment error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def delete_equipment(request, project_name, equipment_id):
    """Move equipment to trash"""
    return InventoryItemViews.delete_item(
        request, project_name, equipment_id, Equipment, TrashEquipment
    )


@login_required
def trash_equipment_(request, project_name):
    """View trashed consumables"""
    try:
        project = get_object_or_404(Project, name=project_name)
        trash_items = TrashConsumable.objects.filter(project=project)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'trash_items': trash_items,
            'item_type': 'consumables',
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/trash_consumables.html', context)

    except Exception as e:
        security_logger.error(f"Trash consumables view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def restore_equipment(request, project_name, trash_id):
    """Restore equipment from trash"""
    return InventoryItemViews.restore_item(
        request, project_name, trash_id, Equipment, TrashEquipment
    )


@login_required
def delete_trash_equipment(request, trash_id):
    """Permanently delete equipment from trash"""
    return InventoryItemViews.permanent_delete(request, trash_id, TrashEquipment)


@login_required
def empty_equipment_trash(request, project_name):
    """Empty equipment trash"""
    return InventoryItemViews.empty_trash(request, project_name, TrashEquipment)

@login_required
def export_equipment_csv(request, project_name):
    """Export equipment to CSV"""
    fields = {
        'name': 'Name',
        'equip_id': 'Equipment ID',
        'serial_num': 'Serial Number',
        'status': 'Status',
        'service_contract_start': 'Service Contract Start',
        'service_contract_end': 'Service Contract End',
        'storage_location': 'Storage Location',
        'vendor': 'Vendor',
        'source': 'Source',
        'operating_temperature': 'Operating Temperature',
        'last_calibration_date': 'Last Calibration Date',
        'next_calibration_date': 'Next Calibration Date',
        'notes': 'Notes',
        'is_active': 'Is Active',
        'created_at': 'Created At',
        'updated_at': 'Updated At'
    }
    return InventoryItemViews.export_csv(
        request, project_name, Equipment, fields, 'equipments'
    )


@login_required
def export_equipment_excel(request, project_name):
    """Export equipment to Excel"""
    fields = {
        'name': 'Name',
        'equip_id': 'Equipment ID',
        'serial_num': 'Serial Number',
        'status': 'Status',
        'service_contract_start': 'Service Contract Start',
        'service_contract_end': 'Service Contract End',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'source': 'Source',
        'operating_temperature': 'Operating Temperature',
        'last_calibration_date': 'Last Calibration Date',
        'next_calibration_date': 'Next Calibration Date',
        'notes': 'Notes',
        'is_active': 'Is Active',
        'created_at': 'Created At',
        'updated_at': 'Updated At'
    }
    return InventoryItemViews.export_excel(
        request, project_name, Equipment, fields, 'equipments'
    )


@login_required
def export_equipemt_txt(request, project_name):
    """Export equipment to text"""
    fields = {
        'name': 'Name',
        'equip_id': 'Equipment ID',
        'serial_num': 'Serial Number',
        'status': 'Status',
        'service_contract_start': 'Service Contract Start',
        'service_contract_end': 'Service Contract End',
        'storage_location': 'Storage Location',
        'threshold_value': 'Threshold Value',
        'vendor': 'Vendor',
        'source': 'Source',
        'operating_temperature': 'Operating Temperature',
        'last_calibration_date': 'Last Calibration Date',
        'next_calibration_date': 'Next Calibration Date',
        'notes': 'Notes',
        'is_active': 'Is Active',
        'created_at': 'Created At',
        'updated_at': 'Updated At'
    }
    return InventoryItemViews.export_txt(
        request, project_name, Equipment, fields, 'equipments'
    )


@login_required
def get_equipment_info(id):
    try:
        equipment = Equipment.objects.get(id=id)

        # Prepare the data to be sent back as a JSON response
        data = {
            'name': clean_text_field(equipment.name),
            'equip_id': clean_text_field(equipment.equip_id),
            'serial_num': clean_text_field(equipment.serial_num),
            'status': clean_text_field(equipment.status),
            'service_contract_start': equipment.service_contract_start,
            'service_contract_end': equipment.service_contract_end,
            'storage_location': clean_text_field(equipment.storage_location),
            'source': equipment.source,
            'operating_temperature': equipment.operating_temperature,
            'last_calibration_date': equipment.last_calibration_date,
            'next_calibration_date': equipment.next_calibration_date,
            'notes': equipment.notes,
            'is_active': equipment.is_active,
            'created_at': equipment.created_at,
            'updated_at': equipment.created_at
        }

        return JsonResponse(data)

    except Equipment.DoesNotExist:
        return JsonResponse({'error': 'Equipment not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def send_equipment_fault_notification(equipment):
    """Send notification about faulty equipment to relevant team members"""
    try:
        # Get recipients - project manager, editors, and members
        recipients = set()
        recipients.add(equipment.project.project_manager.email)
        recipients.update(editor.email for editor in equipment.project.project_editors.all())
        recipients.update(member.email for member in equipment.project.project_members.all())

        # Prepare context
        context = {
            'equipment': equipment,
            'project': equipment.project,
            'type': 'equipment'
        }

        # Use our centralized email function
        send_email_notification(
            subject=f"Faulty Equipment: {equipment.name}",
            template='inventory/non_functional_equipment_email_template.html',
            context=context,
            recipient_list=list(recipients)
        )
    except Exception as e:
        security_logger.error(f"Failed to send equipment fault notification: {str(e)}")


def get_storage_for_user(user, project):
    """Get all storage items available to a user based on their project manager"""
    # Get the effective project manager for this user
    effective_manager = user

    # If user is not a project manager, use their project's manager
    if not user.profile.managed_projects.exists() and project:
        effective_manager = project.project_manager

    # Get all projects managed by this manager
    managed_projects = Project.objects.filter(project_manager=effective_manager, is_active=True)

    # Get storage from all these projects
    shelves = Shelf.objects.filter(project__in=managed_projects, is_active=True)
    racks = Rack.objects.filter(project__in=managed_projects, is_active=True)
    boxes = Box.objects.filter(project__in=managed_projects, is_active=True)

    return {
        'shelves': shelves,
        'racks': racks,
        'boxes': boxes
    }


# Sample Views
@login_required
def samples(request, project_name):
    """List samples view with shared storage options"""
    try:
        project = get_object_or_404(Project, name=project_name)

        # Get samples with related storage data
        samples = Sample.objects.filter(
            project=project,
            is_active=True
        ).select_related('shelf', 'rack', 'box')

        # Get shared storage options for this user
        storage_options = get_storage_for_user(request.user, project)

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(samples, 50)
        try:
            samples_page = paginator.page(page)
        except PageNotAnInteger:
            samples_page = paginator.page(1)
        except EmptyPage:
            samples_page = paginator.page(paginator.num_pages)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'samples': samples_page,
            'shelves': storage_options['shelves'],
            'racks': storage_options['racks'],
            'boxes': storage_options['boxes'],
            'user': request.user,
            'page_obj': samples_page,
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/samples.html', context)

    except Exception as e:
        security_logger.error(f"Samples view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def dashboard_samples(request, project_name):
    return InventoryItemViews.dashboard_view(
        request, project_name, 'dashboard_samples', Sample, 'volume'
    )


@login_required
@ensure_csrf_cookie
def edit_sample(request, sample_id):
    """Edit sample"""
    fields = {
        'sample_id': 'text',
        'sample_type': 'text',
        'description': 'text',
        'collection_date': 'date',
        'country': 'text',
        'volume': 'float',
        'volume_unit': 'text',
        'concentration': 'float',
        'storage_location': 'text',
        'cold_storage_id': 'text',
        'well_id': 'text',
        'date_recorded': 'date',
        'storage_temperature': 'int',
        'threshold_value': 'int',
        'is_active': 'bool',
        'created_at': 'date',
        'updated_at': 'date',
        'notes': 'text'
    }
    return InventoryItemViews.edit_item(request, sample_id, Sample, fields)


@login_required
def delete_sample(request, project_name, sample_id):
    """Move sample to trash"""
    return InventoryItemViews.delete_item(
        request, project_name, sample_id, Sample, TrashSample
    )


@login_required
def trash_samples(request, project_name):
    """View trashed samples"""
    try:
        project = get_object_or_404(Project, name=project_name)
        trash_items = TrashSample.objects.filter(project=project)

        context = {
            'project': project,
            'projects': get_user_projects(request.user),
            'trash_items': trash_items,
            'item_type': 'samples',
            **get_sidebar_urls(project_name)
        }
        return render(request, 'inventory/trash_samples.html', context)

    except Exception as e:
        security_logger.error(f"Trash samples view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def restore_sample(request, project_name, trash_id):
    """Restore sample from trash"""
    return InventoryItemViews.restore_item(
        request, project_name, trash_id, Sample, TrashSample
    )


@login_required
def delete_trash_sample(request, trash_id):
    """Permanently delete sample from trash"""
    return InventoryItemViews.permanent_delete(request, trash_id, TrashSample)


@login_required
def empty_sample_trash(request, project_name):
    """Empty sample trash"""
    return InventoryItemViews.empty_trash(request, project_name, TrashSample)


@login_required
@ensure_csrf_cookie
def retrieve_sample(request, sample_id):
    """Retrieve/use sample items"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        sample = get_object_or_404(Sample, id=sample_id)
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)
        if amount > sample.volume:
            return JsonResponse({'error': 'Not enough sample volume available'}, status=400)

        sample.volume -= amount
        sample.save()

        log_msg = f"{amount} units of sample {sample.sample_id} withdrawn"
        Log.objects.create(
            project=sample.project,
            user=request.user,
            action=log_msg
        )
        # Check threshold and send notification if needed
        if sample.volume < sample.threshold_value:
            threading.Thread(
                target=send_sample_notification,
                args=(sample,)
            ).start()

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': sample.id,
            'sample_id': sample.sample_id,
            'sample_type': sample.sample_type,
            'description': sample.description,
            'collection_date': sample.collection_date,
            'country': sample.country,
            'volume': sample.volume,
            'volume_unit': sample.volume_unit,
            'concentration': sample.concentration,
            'storage_location': sample.storage_location,
            'cold_storage_id': sample.cold_storage_id,
            'well_id': sample.well_id,
            'date_recorded': sample.date_recorded,
            'storage_temperature': sample.storage_temperature,
            'threshold_value': sample.threshold_value,
            'is_active': sample.is_active,
            'created_at': sample.is_active,
            'update_at': sample.updated_at,
            'notes': sample.notes
        })

    except Exception as e:
        security_logger.error(f"Retrieve sample error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def send_sample_notification(sample):
    subject = 'Sample Volume Below Threshold'
    # Add the email address to send the notification
    recipient_list = [sample.project.project_manager.email]

    # Render the HTML template as a string
    html_message = render_to_string(
            'inventory/shortage_email_template.html', {'sample': sample}
    )
    msg = EmailMultiAlternatives(
            subject,
            html_message,
            'settings.EMAIL_HOST_USER',
            recipient_list
    )

    msg.mixed_subtype = 'related'
    msg.attach_alternative(html_message, "text/html")
    email_images = ["Bell.png", "Logo_Orange.png", "Logo_White.png",
                    "facebook2x.png", "instagram2x.png",
                    "linkedin2x.png", "twitter2x.png"]
    for root, _, files in os.walk(f"{static_img_path}/images/"):
        for file in files:
            if file in email_images:
                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                img = MIMEImage(open(file_path, 'rb').read())
                img.add_header('Content-Id', f'<{filename}>')
                msg.attach(img)

    msg.send()


@login_required
@ensure_csrf_cookie
def restock_sample(request, sample_id):
    """Restock sample items to inventory"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        sample = get_object_or_404(Sample, id=sample_id)
        amount = int(request.POST.get('amount', 0))

        if amount <= 0:
            return JsonResponse({'error': 'Amount must be positive'}, status=400)

        sample.volume += amount
        sample.save()

        log_msg = f"{amount} units added to sample {sample.sample_id}"
        Log.objects.create(
            project=sample.project,
            user=request.user,
            action=log_msg
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': log_msg,
            'id': sample.id,
            'sample_id': sample.sample_id,
            'sample_type': sample.sample_type,
            'description': sample.description,
            'collection_date': sample.collection_date,
            'country': sample.country,
            'volume': sample.volume,
            'volume_unit': sample.volume_unit,
            'concentration': sample.concentration,
            'storage_location': sample.storage_location,
            'cold_storage_id': sample.cold_storage_id,
            'well_id': sample.well_id,
            'date_recorded': sample.date_recorded,
            'storage_temperature': sample.storage_temperature,
            'threshold_value': sample.threshold_value,
            'is_active': sample.is_active,
            'created_at': sample.is_active,
            'update_at': sample.updated_at,
            'notes': sample.notes
        })

    except Exception as e:
        security_logger.error(f"Restock sample error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def export_sample_csv(request, project_name):
    """Export samples to CSV"""
    fields = {
        'sample_id': 'Sample ID',
        'sample_type': 'Sample Type',
        'description': 'Description',
        'collection_date': 'Collection Date',
        'country': 'Country',
        'volume': 'Volume',
        'volume_unit': 'Volume Unit',
        'concentration': 'Concentration',
        'storage_location': 'Storage Location',
        'cold_storage_id': 'Cold Storage ID',
        'well_id': 'Well ID',
        'date_recorded': 'Date Recorded',
        'storage_temperature': 'Storage Temperature',
        'threshold_value': 'Threshold Value',
        'created_at': 'Created At',
        'updated_at': 'Updated At',
        'notes': 'Notes'
    }
    return InventoryItemViews.export_csv(
        request, project_name, Sample, fields, 'samples'
    )


@login_required
def export_sample_excel(request, project_name):
    """Export samples to Excel"""
    fields = {
        'sample_id': 'Sample ID',
        'sample_type': 'Sample Type',
        'description': 'Description',
        'collection_date': 'Collection Date',
        'country': 'Country',
        'volume': 'Volume',
        'volume_unit': 'Volume Unit',
        'concentration': 'Concentration',
        'storage_location': 'Storage Location',
        'cold_storage_id': 'Cold Storage ID',
        'well_id': 'Well ID',
        'date_recorded': 'Date Recorded',
        'storage_temperature': 'Storage Temperature',
        'threshold_value': 'Threshold Value',
        'created_at': 'Created At',
        'updated_at': 'Updated At',
        'notes': 'Notes'
    }
    return InventoryItemViews.export_excel(
        request, project_name, Sample, fields, 'samples'
    )


@login_required
def export_sample_txt(request, project_name):
    """Export samples to text"""
    fields = {
        'sample_id': 'Sample ID',
        'sample_type': 'Sample Type',
        'description': 'Description',
        'collection_date': 'Collection Date',
        'country': 'Country',
        'volume': 'Volume',
        'volume_unit': 'Volume Unit',
        'concentration': 'Concentration',
        'storage_location': 'Storage Location',
        'cold_storage_id': 'Cold Storage ID',
        'well_id': 'Well ID',
        'date_recorded': 'Date Recorded',
        'storage_temperature': 'Storage Temperature',
        'threshold_value': 'Threshold Value',
        'created_at': 'Created At',
        'updated_at': 'Updated At',
        'notes': 'Notes'
    }
    return InventoryItemViews.export_txt(
        request, project_name, Sample, fields, 'samples'
    )


@login_required
@ensure_csrf_cookie
def add_sample(request, project_name):
    """Add a new sample with shared storage hierarchy support"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)

    try:
        project = get_object_or_404(Project, name=project_name)

        # Extract storage hierarchy data
        shelf_id = request.POST.get('shelf')
        shelf_name = clean_text_field(request.POST.get('new_shelf_name', ''))
        shelf_code = clean_text_field(request.POST.get('new_shelf_code', ''))
        shelf_capacity = clean_text_field(request.POST.get('new_shelf_capacity', ''))
        shelf_notes = clean_text_field(request.POST.get('new_shelf_notes', ''))

        rack_id = request.POST.get('rack')
        rack_name = clean_text_field(request.POST.get('new_rack_name', ''))
        rack_capacity = clean_text_field(request.POST.get('new_rack_capacity', ''))
        rack_notes = clean_text_field(request.POST.get('new_rack_notes', ''))

        box_id = request.POST.get('box')
        box_name = clean_text_field(request.POST.get('new_box_name', ''))
        box_row_count = clean_text_field(request.POST.get('new_box_row_count', ''))
        box_column_count = clean_text_field(request.POST.get('new_box_column_count', ''))
        box_notes = clean_text_field(request.POST.get('new_box_notes', ''))

        # Handle storage hierarchy creation/selection
        shelf = None
        rack = None
        box = None

        # Get available storage for this user
        storage_options = get_storage_for_user(request.user, project)

        # Process Shelf
        if shelf_id and shelf_id != 'new':
            # Allow selection from any shelf belonging to the manager's projects
            shelf = get_object_or_404(Shelf, id=shelf_id, project__in=storage_options['shelves'].values('project'))
        elif shelf_name and shelf_code and shelf_capacity and shelf_notes:
            # Create new shelf in the current project
            shelf, created = Shelf.objects.get_or_create(
                project=project,  # Create in current project
                name=shelf_name,
                location_code=shelf_code,
                capacity=shelf_capacity,
                notes=shelf_notes
            )
            if created:
                Log.objects.create(
                    project=project,
                    user=request.user,
                    action=f'Created new shelf: {shelf_name}'
                )

        # Process Rack
        if rack_id and rack_id != 'new' and shelf:
            # Allow selection from any rack belonging to the manager's projects
            rack = get_object_or_404(Rack, id=rack_id, project__in=storage_options['racks'].values('project'))

            # Validate that rack belongs to selected shelf if shelf is specified
            if shelf and rack.shelf != shelf:
                return JsonResponse({'error': 'Selected rack does not belong to the selected shelf'}, status=400)

        elif rack_name and rack_capacity and rack_notes and shelf:
            # Create new rack in the shelf's project
            rack, created = Rack.objects.get_or_create(
                project=shelf.project,  # Use the same project as the shelf
                shelf=shelf,
                name=rack_name,
                capacity=rack_capacity,
                notes=rack_notes,
            )
            if created:
                Log.objects.create(
                    project=project,
                    user=request.user,
                    action=f'Created new rack: {rack_name} in shelf {shelf.name}'
                )

        # Process Box
        if box_id and box_id != 'new' and rack:
            # Allow selection from any box belonging to the manager's projects
            box = get_object_or_404(Box, id=box_id, project__in=storage_options['boxes'].values('project'))

            # Validate that box belongs to selected rack if rack is specified
            if rack and box.rack != rack:
                return JsonResponse({'error': 'Selected box does not belong to the selected rack'}, status=400)

        elif box_name and box_row_count and box_column_count and box_notes and rack:
            # Create new box in the rack's project
            box, created = Box.objects.get_or_create(
                project=rack.project,  # Use the same project as the rack
                rack=rack,
                name=box_name,
                row_count=box_row_count,
                column_count=box_column_count,
                notes=box_notes
            )
            if created:
                Log.objects.create(
                    project=project,
                    user=request.user,
                    action=f'Created new box: {box_name} in rack {rack.name}'
                )

        # Prepare sample data (same as before)
        data = {
            'sample_id': clean_text_field(request.POST.get('sample_id', '')),
            'sample_type': clean_text_field(request.POST.get('sample_type', '')),
            'collection_date': datetime.strptime(request.POST.get('collection_date', ''), '%Y-%m-%d').date() if request.POST.get('collection_date') else None,
            'date_recorded': datetime.strptime(request.POST.get('date_recorded', ''), '%Y-%m-%d').date() if request.POST.get('date_recorded') else date.today(),
            'country': clean_text_field(request.POST.get('country', '')),
            'volume': float(request.POST.get('volume', 0)),
            'volume_unit': clean_text_field(request.POST.get('volume_unit', 'mL')),
            'concentration': float(request.POST.get('concentration', 0)) if request.POST.get('concentration') else None,
            'storage_location': clean_text_field(request.POST.get('storage_location', '')),
            'cold_storage_id': clean_text_field(request.POST.get('cold_storage_id', '')),
            'storage_temperature': int(request.POST.get('storage_temperature', 0)) if request.POST.get('storage_temperature') else None,
            'well_id': clean_text_field(request.POST.get('well_id', '')),
            'threshold_value': int(request.POST.get('threshold_value', 0)) if request.POST.get('threshold_value') else None,
            'notes': clean_text_field(request.POST.get('notes', '')),
        }

        # Create the sample with storage hierarchy
        with transaction.atomic():
            sample = Sample.objects.create(
                project=project,
                shelf=shelf,
                rack=rack,
                box=box,
                **data
            )

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Added sample {sample.sample_id}'
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'id': sample.id,
            'message': 'Sample added successfully'
        })

    except IntegrityError as e:
        return JsonResponse({'error': 'A storage item with this name or code already exists'}, status=400)
    except ValidationError as e:
        errors = handle_validation_error(e)
        return JsonResponse({'errors': errors}, status=400)
    except Exception as e:
        security_logger.error(f"Add sample error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_storage_options(request, project_name):
    """Get storage hierarchy options across all manager's projects"""
    try:
        project = get_object_or_404(Project, name=project_name)
        storage_options = get_storage_for_user(request.user, project)

        shelves = storage_options['shelves'].values('id', 'name', 'location_code', 'project__name')
        racks = storage_options['racks'].values('id', 'name', 'location_code', 'shelf_id', 'project__name')
        boxes = storage_options['boxes'].values('id', 'name', 'location_code', 'rack_id', 'project__name')

        return JsonResponse({
            'shelves': list(shelves),
            'racks': list(racks),
            'boxes': list(boxes)
        })

    except Exception as e:
        security_logger.error(f"Get storage options error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def create_shelf(request, project_name):
    """Create a new shelf"""
    try:
        project = get_object_or_404(Project, name=project_name)
        name = clean_text_field(request.POST.get('name'))
        location_code = clean_text_field(request.POST.get('location_code'))
        capacity = clean_text_field(request.POST.get('capacity'))
        notes = clean_text_field(request.POST.get('notes'))

        shelf = Shelf.objects.create(
            project=project,
            name=name,
            location_code=location_code,
            capacity=capacity,
            notes=notes
        )

        return JsonResponse({
            'success': True,
            'id': shelf.id,
            'name': shelf.name,
            'location_code': shelf.location_code,
            'capacity': shelf.capacity
        })

    except IntegrityError:
        return JsonResponse({'error': 'A shelf with this name or location code already exists'}, status=400)
    except Exception as e:
        security_logger.error(f"Create shelf error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def create_rack(request, shelf_id):
    """Create a new rack"""
    try:
        shelf = get_object_or_404(Shelf, name=shelf_id)
        name = clean_text_field(request.POST.get('name'))
        capacity = clean_text_field(request.POST.get('capacity'))
        notes = clean_text_field(request.POST.get('notes'))

        rack = Rack.objects.create(
            project=shelf.project,
            shelf=shelf,
            name=name,
            capacity=capacity,
            notes=notes
        )

        return JsonResponse({
            'success': True,
            'id': rack.id,
            'name': rack.name,
            'capacity': rack.capacity
        })

    except IntegrityError:
        return JsonResponse({'error': 'A rack with this name already exists'}, status=400)
    except Exception as e:
        security_logger.error(f"Create rack error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def create_box(request, rack_id):
    """Create a new box"""
    try:
        rack = get_object_or_404(Rack, name=rack_id)
        name = clean_text_field(request.POST.get('name'))
        row_count = clean_text_field(request.POST.get('row_count'))
        column_count = clean_text_field(request.POST.get('column_count'))
        notes = clean_text_field(request.POST.get('notes'))

        box = Box.objects.create(
            project=rack.project,
            rack=rack,
            name=name,
            row_count=row_count,
            column_count=column_count,
            notes=notes
        )

        return JsonResponse({
            'success': True,
            'id': box.id,
            'name': box.name,
            'row_count': box.row_count,
            'column_count': box.column_count
        })

    except IntegrityError:
        return JsonResponse({'error': 'A box with this name already exists'}, status=400)
    except Exception as e:
        security_logger.error(f"Create box error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_sample_info(id):
    try:
        sample = Sample.objects.get(id=id)

        # Prepare the data to be sent back as a JSON response
        data = {
            'sample_id': clean_text_field(sample.sample_id),
            'sample_type': clean_text_field(sample.sample_type),
            'description': clean_text_field(sample.description),
            'country': clean_text_field(sample.country),
            'volume': sample.volume,
            'well_id': clean_text_field(sample.well_id),
            'date_recorded': sample.date_recorded,
            'storage_location': clean_text_field(sample.storage_location),
            'threshold_value': sample.threshold_value,
        }

        return JsonResponse(data)

    except Sample.DoesNotExist:
        return JsonResponse({'error': 'Sample not found'}, status=404)
    except Exeception as e:
        return JsonResponse({'error': str(e)}, status=400)


# MSDS Views
def handle_msds_upload(uploaded_file, reagent, user):
    """Helper function for handling upload of new MSDS file"""
    try:
        # Check for duplicate files
        # if MSDSFile.objects.filter(file_hash=file_hash, reagent=reagent).exists():
        #    raise ValidationError('This MSDS file already exists for this reagent')

        # Create temporary file for scanning
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        # Start virus scan synchronously
        try:
            if settings.CLAMAV_ENABLED:
                cd = pyclamd.ClamdUnixSocket(settings.CLAMAV_SOCKET)
                scan_result = cd.scan_file(tmp_path)

                if scan_result is not None:
                    os.unlink(tmp_path)  # Clean up temp file
                    virus_name = scan_result.get(tmp_path, 'Unknown virus')
                    security_logger.warning(
                            f"Virus detected in uploaded MSDS: {virus_name}",
                            extra={'reagent_id': reagent.id, 'file_name': uploaded_file.name}
                    )
                    raise ValidationError(
                        f'Virus detected: {virus_name}. File not saved.'
                    )
        except Exception as e:
            os.unlink(tmp_path)  # Cleanup temp file on error
            security_logger.error(
                    f"Virus scan failed: {str(e)}",
                    extra={'reagent_id': reagent.id, 'file_name': uploaded_file.name}
            )
            if settings.DEBUG:
                pass    # In dev, allow bypassing scan errors
            else:
                raise ValidationError(
                    'Virus scan failed. Please try again or contact support.'
                )

        # Delete old MSDS if exists
        reagent.msds_files.all().delete()

        # Create MSDS record after passing checks
        msds_file = MSDSFile(
                reagent=reagent,
                uploaded_by=user,
                scan_result='clean'
        )

        # Temporarily bypass to get PK (bypasses validation since no file)
        msds_file.save()

        # Now attach file
        msds_file.file = uploaded_file
        msds_file.full_clean()  # Explicit Validation

        # Include metadata
        msds_file.original_filename = uploaded_file.name
        msds_file.file_size = uploaded_file.size
        msds_file.file_hash = msds_file.calculate_file_hash()

        # Save again with all data(meta)
        msds_file.save()

        # Clean up temp file
        os.unlink(tmp_path)

        msds_log = Log.objects.create(
                project=reagent.project,
                user=user,
                action=f'Uploaded MSDS for {reagent.name}'
        )

    except ValidationError as e:
        # Delete the object if validation fails
        msds_file.delete()
        msds_log.delete()
        raise e
    except Exception as e:
        security_logger.error(f'Error in MSDS upload: {str(e)}')
        return JsonResponse({'Error': "Oops, something went wrong"})


@login_required
@csrf_exempt
def upload_msds(request, project_name, reagent_id):
    """Upload new MSDS file with proper virus scanning flow"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        reagent = get_object_or_404(Reagent, id=reagent_id, project__name=project_name)
        uploaded_file = request.FILES.get('msds_file')

        if not uploaded_file:
            return JsonResponse({'error': "No file provided"}, status=400)

        # 1. Validate file size first (quick check)
        if uploaded_file.size > 5 * 1024 * 1024:  # 5MB limit
            return JsonResponse({'error': 'File size exceeds 5MB limit'}, status=400)

        # 2. Validate PDF structure (without saving)
        try:
            # Read the file into memory for validation
            file_content = uploaded_file.read()
            reader = PdfReader(io.BytesIO(file_content))
            if len(reader.pages) == 0:
                return JsonResponse({'error': "PDF appears to be empty"}, status=400)
        except PdfReadError:
            return JsonResponse({'error': "Invalid PDF file"}, status=400)
        finally:
            uploaded_file.seek(0)  # Reset file pointer

        # 3. Calculate file hash for deduplication
        file_hash = hashlib.sha256(file_content).hexdigest()

        # Check for duplicate files
        if MSDSFile.objects.filter(file_hash=file_hash, reagent=reagent).exists():
            return JsonResponse({'error': 'This MSDS file already exists for this reagent'}, status=400)

        # 4. Create temporary file for scanning
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            for chunk in uploaded_file.chunks():
                tmp_file.write(chunk)
            tmp_path = tmp_file.name

        # 5. Start virus scan synchronously (for immediate feedback)
        try:
            if settings.CLAMAV_ENABLED:
                cd = pyclamd.ClamdUnixSocket(settings.CLAMAV_SOCKET)
                scan_result = cd.scan_file(tmp_path)

                if scan_result is not None:
                    os.unlink(tmp_path)  # Clean up temp file
                    virus_name = scan_result.get(tmp_path, 'Unknown virus')
                    security_logger.warning(
                        f"Virus detected in uploaded MSDS: {virus_name}",
                        extra={'reagent_id': reagent_id, 'file_name': uploaded_file.name}
                    )
                    return JsonResponse({
                        'error': f'Virus detected: {virus_name}. File not saved.',
                        'infected': True
                    }, status=400)
        except Exception as e:
            os.unlink(tmp_path)  # Clean up temp file on error
            security_logger.error(
                f"Virus scan failed: {str(e)}",
                extra={'reagent_id': reagent_id, 'file_name': uploaded_file.name}
            )
            if settings.DEBUG:
                # In development, allow bypassing scan errors
                pass
            else:
                return JsonResponse({
                    'error': 'Virus scan failed. Please try again or contact support.',
                    'scan_error': True
                }, status=500)

        # 6. Only after passing all checks, create the MSDS record
        msds_file = MSDSFile.objects.create(
            reagent=reagent,
            uploaded_by=request.user,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            file_hash=file_hash,
            scan_result='clean'  # Mark as clean since we scanned synchronously
        )

        # 7. Save the file to the model's file field
        with open(tmp_path, 'rb') as clean_file:
            msds_file.file.save(uploaded_file.name, File(clean_file))

        # 8. Clean up temp file
        os.unlink(tmp_path)

        Log.objects.create(
            project=reagent.project,
            user=request.user,
            action=f'Uploaded MSDS for {reagent.name}'
        )

        return JsonResponse({
            'success': True,
            'refresh': True,
            'message': 'MSDS uploaded successfully',
            'msds_id': msds_file.id
        })

    except Exception as e:
        security_logger.error(f"MSDS upload error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def reagent_msds_files(request, project_name, reagent_id):
    """Get the MSDS file for a reagent"""
    try:
        reagent = get_object_or_404(Reagent, id=reagent_id, project__name=project_name)
        msds_files = reagent.msds_files.all().values(
            'id',
            'original_filename',
            'uploaded_by',
            'upload_date',
            'scan_result'
        )

        # Convert to list and add download URL
        msds_files_list = []
        for msds in msds_files:
            msds_files_list.append({
                'id': msds['id'],
                'filename': msds['original_filename'],
                'uploaded_by': msds['uploaded_by'],
                'upload_date': msds['upload_date'].strftime('%Y-%m-%d %H:%M'),
                'scan_result': msds['scan_result'],
                'download_url': reverse('download_msds', kwargs={'msds_id': msds['id']})
            })

        return JsonResponse({
            'msds_files': msds_files_list
        })

    except Exception as e:
        security_logger.error(f"MSDS files view error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def download_msds(request, msds_id):
    """Download MSDS file"""
    msds = get_object_or_404(MSDSFile, id=msds_id)

    # Verify user has access to this MSDS file's project
    if not (request.user == msds.reagent.project.project_manager or 
            request.user in msds.reagent.project.project_editors.all() or
            request.user in msds.reagent.project.project_members.all()):
        return JsonResponse({'error': 'Unauthorized access'}, status=403)

    if not msds.file:
        return JsonResponse({'error': 'File not found'}, status=404)

    response = HttpResponse(msds.file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{msds.original_filename}"'
    response['X-Content-Type-Options'] = 'nosniff'

    Log.objects.create(
            project=msds.reagent.project,
            user=request.user,
            action=f"Downloaded MSDS file {msds.original_filename} for {msds.reagent.name}"
    )
    return response


@login_required
def delete_msds(request, msds_id):
    """Delete MSDS file"""
    if request.method != 'POST':
        return JsonResponse({'error': "Invalid request method"}, status=405)

    try:
        msds = get_object_or_404(MSDSFile, id=msds_id)

        # Check permissions
        if not (request.user == msds.reagent.project.project_manager or 
                request.user in msds.reagent.project.project_editors.all()):
            security_logger.error(f"User {request.user.first_name} {request.user.last_name} tried to delete this MSDS file {msds.original_filename}")
            return JsonResponse({
                'error': "Unauthorized",
                'message': "You do not have the permission to perform this operation"
            }, status=403)

        msds.delete()

        Log.objects.create(
            project=msds.reagent.project,
            user=request.user,
            action=f'Deleted MSDS file {msds.original_filename} for {msds.reagent.name}'
        )

        return JsonResponse({
            'success': True,
            'message': 'MSDS file deleted successfully'
        })

    except Exception as e:
        security_logger.error(f"Delete MSDS error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def msds_upload_path(instance, filename):
    """Generate secure path for MSDS files with user/project context"""
    user_id = instance.uploaded_by.id if instance.uploaded_by else 'anonymous'
    project_id = instance.reagent.project.id
    ext = filename.split('.')[-1].lower()

    # Secure filename with UUID and original extension
    unique_filename = f"{uuid.uuid4()}.{ext}"

    return os.path.join(
        'private', 'msds_files',
        f'project_{project_id}',
        f'user_{user_id}',
        unique_filename
    )


@login_required
def bulk_export_reagents(request, project_name):
    """Export selected reagents to CSV"""
    try:
        project = get_object_or_404(Project, name=project_name)

        # Get selected reagent IDs from query parameters
        reagent_ids = request.GET.getlist('ids')

        if not reagent_ids:
            return JsonResponse({'error': 'No reagents selected for export'}, status=400)

        # Get reagents with permission check
        reagents = Reagent.objects.filter(
            id__in=reagent_ids,
            project=project,
            is_active=True
        )

        # Verify user has access to all selected reagents
        if not reagents[0].can_access(request.user):
            return JsonResponse({'error': 'Unauthorized access to some reagents'}, status=403)

        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="reagents_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)

        # Write header
        writer.writerow([
            'Name', 'Product Code', 'Items Per Pack', 'Items Left in Pack',
            'Pack Count', 'Expiry Date', 'Storage Location', 'Storage Condition',
            'Optimal Temperature', 'Vendor', 'Country of Origin', 'Hazard Level',
            'Threshold Value', 'Notes'
        ])

        # Write data
        for reagent in reagents:
            writer.writerow([
                reagent.name,
                reagent.product_code,
                reagent.items_per_pack,
                reagent.items_left_in_pack,
                reagent.pack_count,
                reagent.expiry_date.strftime('%Y-%m-%d') if reagent.expiry_date else '',
                reagent.storage_location,
                reagent.cold_storage,
                f"{reagent.oem_temperature}°{reagent.temperature_unit}" if reagent.oem_temperature else '',
                reagent.vendor,
                reagent.country_of_origin,
                reagent.hazard_level,
                reagent.threshold_value,
                reagent.notes
            ])

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Exported {len(reagent_ids)} reagents to CSV'
        )

        return response

    except Exception as e:
        security_logger.error(f"Bulk export error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def bulk_delete_reagents(request, project_name):
    """Bulk delete reagents endpoint"""
    try:
        reagent_ids = request.POST.getlist('reagent_ids')
        project = get_object_or_404(Project, name=project_name)

        if not reagent_ids:
            return JsonResponse({'error': 'No reagents selected for deletion'}, status=400)

        reagents = Reagent.objects.filter(
            id__in=reagent_ids, 
            project=project,
            is_active=True
        )

        # Verify user has permission to delete each reagent
        if reagents[0].is_just_member(request.user):
            return JsonResponse({'error': 'Unauthorized access to perform this operation'}, status=403)

        deleted_count = 0
        for reagent in reagents:
            # Move to trash
            trash_data = {
                'original_id': reagent.id,
                'project': reagent.project,
                'name': reagent.name,
                'product_code': reagent.product_code,
                'items_per_pack': reagent.items_per_pack,
                'items_left_in_pack': reagent.items_left_in_pack,
                'pack_count': reagent.pack_count,
                'expiry_date': reagent.expiry_date,
                'date_recorded': reagent.date_recorded,
                'cold_storage': reagent.cold_storage,
                'oem_temperature': reagent.oem_temperature,
                'temperature_unit': reagent.temperature_unit,
                'country_of_origin': reagent.country_of_origin,
                'vendor': reagent.vendor,
                'threshold_value': reagent.threshold_value,
                'storage_location': reagent.storage_location,
                'deleted_by': request.user
            }

            TrashReagent.objects.create(**trash_data)
            reagent.delete()
            deleted_count += 1

        Log.objects.create(
            project=project,
            user=request.user,
            action=f'Bulk deleted {deleted_count} reagents'
        )

        return JsonResponse({
            'success': True,
            'deleted_count': deleted_count,
            'total_selected': len(reagent_ids),
            'message': f'Successfully deleted {deleted_count} out of {len(reagent_ids)} selected reagents'
        })

    except Exception as e:
        security_logger.error(f"Bulk delete error: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
