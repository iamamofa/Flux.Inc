from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login,logout
from django.contrib import messages
from django.contrib.auth import views as auth_views
from .models import *
from .forms import *
from django.http import JsonResponse
import json
from django.http import HttpResponse
import csv
from openpyxl import Workbook
from django.core.mail import send_mail
import threading
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import EmailMultiAlternatives
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import mimetypes
import os
from email.mime.image import MIMEImage
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            logout(request)
            message1 = 'Your password has been changed successfully'
            message2 = 'Try logging in again to use your account'
            return render(request, 'inventory/success_page.html', {'message1': message1, 'message2': message2})
        else:
            messages.error(request, 'Try again')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'inventory/settings.html', {'form': form})

def user_application(request):
    form = UserApplicationForm()
    if request.method == 'POST':
        form = UserApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save()

            message1 = 'Your information has been uploaded.We would review it and get back to you shortly.'
            message2 = 'If you do not receive a mail in the next 24 hours, do well to reach out via mail.'
            return render(request, 'inventory/confirmed_registration.html', {'message1': message1, 'message2': message2})
           
        else:
            form = UserApplicationForm()

    return render(request, 'inventory/user_application.html', {'form': form})

def home(request):
    return render(request, 'inventory/home.html')

def registration_page(request):
    return render(request, 'inventory/registration_page.html')

def register_project_manager(request):
    email = request.GET.get('email')
    first_name = request.GET.get('first_name')
    last_name = request.GET.get('last_name')

    if email and first_name and last_name:
        # The email, first name, and last name values are available
        initial_data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name
        }
        form = ProjectManagerSignUpForm(initial=initial_data)
    
    if request.method == 'POST':
        form = ProjectManagerSignUpForm(request.POST, request=request)
        if form.is_valid():
            try: 
                project_name = form.cleaned_data['project_name']
                user = form.save()
                login(request, user)

                # Create a user profile for the project manager
                user_profile = UserProfile.objects.create(user=user)
                
                # Create a new project using the entered project name
                project = Project.objects.create(name=project_name, project_manager=user)
                
                # Add the project to the project manager's user profile
                user_profile.managed_projects.add(project)
                
                return redirect(f'/consumables/{project_name}')
            except ValidationError as e:
                form.add_error('project_name', str(e))
    else:
        form = ProjectManagerSignUpForm(request=request)

    return render(request, 'inventory/register_project_manager.html', {'form': form, 'email': email, 'first_name': first_name, 'last_name': last_name})


def register_user(request):
    if request.method == 'POST':
        form = EditorMemberSignUpForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            login(request, user)
            user_profile = UserProfile.objects.create(user=user)
            # print(f'pm_email: {form.cleaned_data["pm_email"]}')

            return render(request, 'inventory/user_account_created.html')
    else:
        form = EditorMemberSignUpForm(request=request)

    return render(request, 'inventory/register_user.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                user_profile = UserProfile.objects.get(user=user)
                projects = user_profile.managed_projects.all()
                first_project = projects.first()
                if first_project:
                    first_project_name = first_project.name
                    return redirect(f'/consumables/{first_project_name}')
                else:
                    message1 = 'Sorry, you do not seem to have a project associated with this account.'
                    message2 = 'Reach out to your project coordinator to be added to a project or contact us for further assistance.'
                    return render(request, 'inventory/404_page.html', {'message1': message1, 'message2': message2})
            else:
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()
    
    return render(request, 'inventory/login.html', {'form': form})

def logoutUser(request):
    logout(request)
    return redirect('login')

def team(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    team_members = project.project_editors.all() | project.project_members.all()
    context = {'project': project, 'projects': projects,'team_members': team_members}
    return render(request, 'inventory/team.html', context)

def log(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    logs = Log.objects.filter(project=project).order_by('-id')
    context = {'project': project, 'projects': projects,'logs': logs}
    return render(request, 'inventory/logs.html', context)

def add_user_to_project(request, project_name):
    project = get_object_or_404(Project, name=project_name)
    try:
        if request.method == 'POST':
            email = request.POST.get('email')
            role = request.POST.get('role')

            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                message1 = 'Sorry, the email you entered does not seem to exist in our database.'
                message2 = 'Kindly ensure that the individual you are trying to add is registered.'
                return render(request, 'inventory/404_page.html', {'message1': message1, 'message2': message2})
                
            
            if project.project_editors.filter(email=email).exists() or project.project_members.filter(email=email).exists():
                message1 = 'The individual has already been added to the project.'
                message2 = 'If this is not the case, kindly do well to reach out.'
                return render(request, 'inventory/404_page.html', {'message1': message1, 'message2': message2})
            else:
                if role == 'Full':
                    project.project_editors.add(user)
                    user_profile = UserProfile.objects.get(user=user)
                    user_profile.managed_projects.add(project)
                elif role == 'Limited':
                    project.project_members.add(user)
                    user_profile = UserProfile.objects.get(user=user)
                    user_profile.managed_projects.add(project)

                log_entry = Log.objects.create(project=project,user=request.user,action=f'{user.first_name} {user.last_name} added')

                return redirect(f'/team/{project_name}')
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def remove_user(request,project_name,id):
    try:
        user = User.objects.get(id=id)
        project = get_object_or_404(Project, name=project_name)
        
        if user in project.project_editors.all():
            # User is a project editor, remove from project_editors
            project.project_editors.remove(user)
        
        if user in project.project_members.all():
            # User is a project member, remove from project_members
            project.project_members.remove(user)
        
        user_profile = UserProfile.objects.get(user=user)
        
        # Remove the project from the user's managed_projects field
        user_profile.managed_projects.remove(project)

        # Save the user_profile to update the changes
        user_profile.save()
        
        # Save the project to update the changes
        project.save()

        log_entry = Log.objects.create(project=project,user=request.user,action=f'{user.first_name} {user.last_name} removed')

        return JsonResponse({'message': 'User removed successfully'}, status=200)

    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def edit_user_access(request,project_name,id):
    user = User.objects.get(id=id)
    project = get_object_or_404(Project, name=project_name)

    if request.method == 'PUT':
        # Assuming the request body contains the updated consumable data as JSON

        # Extract the data from the request body
        data = json.loads(request.body)
        role = data.get('role', 0)

        if role == 'Full':
            project.project_members.remove(user)
            project.project_editors.add(user)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{user.first_name} {user.last_name} given full access')
            
        elif role == 'Limited':
            project.project_editors.remove(user)
            project.project_members.add(user)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{user.first_name} {user.last_name} given limited access')

        # Save the changes
        project.save()

        # Return a JSON response indicating success
        return JsonResponse({'message': f'User with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating user with ID {id}.'}, status=400)

@login_required
def create_project(request):
    if request.method == 'PUT':
            data = json.loads(request.body)

            project_name = str(data.get('project_name', 0))
            project_manager = request.user
            
            # Create the new project
            project = Project.objects.create(name=project_name, project_manager=project_manager)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{project_name} added to Projects')

            # Retrieve the project manager's user profile
            try:
                user_profile = UserProfile.objects.get(user=project_manager)
                user_profile.managed_projects.add(project)

                # return redirect(f'/consumables/{project_name}')
            except UserProfile.DoesNotExist:
                pass

            return JsonResponse({'message': f'Project created successfully'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error creating project'}, status=400)

@login_required(login_url='login')
def consumables(request,project_name):
    # projects = Project.objects.all()
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)

    if project:
        projects = user_profile.managed_projects.all()
        # Retrieve the project object based on the provided project name
        

        # Retrieve all the consumables related to the project
        consumables = project.consumable_set.all()

        context = {'project': project, 'projects': projects,'consumables': consumables, 'user': user}
        return render(request, 'inventory/consumables.html', context)

def addConsumable(request, project_name):
    try:
        if request.method == 'POST':
            # Retrieve the form data from the request
            project = Project.objects.get(name=project_name)
            name = request.POST.get('name')
            product_code = request.POST.get('product_code')
            pack_size = request.POST.get('pack_size')
            quantity = request.POST.get('quantity')
            expiry_date = request.POST.get('expiry_date')
            storage_location = request.POST.get('storage_location')
            threshold_value = request.POST.get('threshold_value')
            # Create a new Consumable instance associated with the active project
            consumable = Consumable.objects.create(project=project, name=name, product_code=product_code, pack_size=pack_size, pack_size_rem=pack_size, quantity=quantity, expiry_date=expiry_date, storage_location=storage_location, threshold_value=threshold_value)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{name} added to Consumables')
        
            return redirect(f'/consumables/{project_name}')
            # return JsonResponse({'message': 'Consumable created successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def dashboard_consumables(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    consumables = project.consumable_set.all()

    # Prepare data for Plotly.js
    names = []
    quantities = []
    for consumable in consumables:
        names.append(consumable.name)
        quantities.append(consumable.quantity)
    
    data = {'names': names, 'quantities': quantities}
    plot_data = json.dumps(data)

    # Render the template with the plot data
    return render(request, 'inventory/dashboard_consumables.html', {'plot_data': plot_data,'project': project, 'projects': projects,'consumables': consumables})

def trash_consumables(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    trash_consumables = project.trashconsumable_set.all()
    context = {'project': project, 'projects': projects,'trash_consumables': trash_consumables}
    return render(request, 'inventory/trash_consumables.html', context)
    
def get_consumable_info(request, id):
    consumable = get_object_or_404(Consumable, id=id)
    
    # Prepare the data to be sent back as a JSON response
    data = {
        'name': consumable.name,
        'product_code': consumable.product_code,
        'pack_size': consumable.pack_size,
        'pack_size_rem': consumable.pack_size_rem,
        'quantity': consumable.quantity,
        'expiry_date': consumable.expiry_date,
        'date_recorded': consumable.date_recorded,
        'storage_location': consumable.storage_location,
        'threshold_value': consumable.threshold_value,
        
    }
    
    return JsonResponse(data)

def edit_consumable(request, id):
    consumable = get_object_or_404(Consumable, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated consumable data as JSON

        # Extract the data from the request body
        data = json.loads(request.body)

        # Update the consumable with the new data
        consumable.name = data.get('name', consumable.name)
        consumable.product_code = data.get('product_code', consumable.product_code)
        consumable.pack_size = data.get('pack_size', consumable.pack_size)
        consumable.quantity = data.get('quantity', consumable.quantity)
        consumable.expiry_date = data.get('expiry_date ', consumable.expiry_date )
        consumable.storage_location = data.get('storage_location', consumable.storage_location)
        consumable.threshold_value = data.get('threshold_value', consumable.threshold_value)
        # Update other fields accordingly
        log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{consumable.name} details edited')
        # Save the changes
        consumable.save()

        # Return a JSON response indicating success
        return JsonResponse({'message': f'Consumable with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating consumable with ID {id}.'}, status=400)

def retrieve_consumable(request, id):
    consumable = get_object_or_404(Consumable, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated consumable data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        option = data.get('retrieve_by', 0)

        amount = data.get('amount', 0)

        if option == 'Pack size':
            tmp = int(consumable.pack_size_rem) - int(amount)
            if tmp == 0:
                consumable.quantity = int(consumable.quantity) - 1
                consumable.pack_size_rem = consumable.pack_size
                log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'1 {consumable.name} taken from stock')
            elif tmp > 0:
                consumable.pack_size_rem = tmp
                log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} removed from {consumable.name} pack')
            else:
                if abs(tmp)%consumable.pack_size == 0:
                    consumable.quantity = int(consumable.quantity) - int(abs(tmp)/consumable.pack_size) - 1
                    consumable.pack_size_rem = consumable.pack_size
                    log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{int(abs(tmp)/consumable.pack_size) - 1} {consumable.name} taken from stock')
                else:
                    consumable.quantity = int(consumable.quantity) - int(abs(tmp)/consumable.pack_size) - 1
                    consumable.pack_size_rem = consumable.pack_size - abs(tmp)%consumable.pack_size
                    log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} removed from {consumable.name} pack')
                    
        else:
            consumable.quantity = int(consumable.quantity) - int(amount)
            log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} {consumable.name} taken from stock')

        # Save the changes
        # log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{quantity_to_subtract} {consumable.name} taken from stock')
        consumable.save()
        if consumable.quantity < consumable.threshold_value:
            email_thread = threading.Thread(target=send_consumable_notification, args=(consumable,))
            email_thread.start()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Consumable with ID {id} updated successfully.'})
        # return redirect(f'/consumables/{consumable.project.name}')

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating consumable with ID {id}.'}, status=400)

def send_consumable_notification(consumable):
    subject = 'Consumable Quantity Below Threshold'
    message = f"The quantity of {consumable.name} is below the threshold. Please take necessary action."
    recipient_list = [consumable.project.project_manager.email]  # Add the email address to send the notification

     # Render the HTML template as a string
    html_message = render_to_string('inventory/shortage_email_template.html', {'consumable': consumable})
    # send_mail(subject, message, 'settings.EMAIL_HOST_USER', recipient_list, fail_silently=False)
    msg = EmailMultiAlternatives(subject, html_message, 'settings.EMAIL_HOST_USER', recipient_list)

    msg.mixed_subtype = 'related'
    msg.attach_alternative(html_message, "text/html")
    email_images = ["Bell.png", "Logo_Orange.png", "Logo_White.png", "facebook2x.png", "instagram2x.png", "linkedin2x.png", "twitter2x.png"]
    for root, dirs, files in os.walk('C:/Users/HP/Desktop/inventory_system/static/images/'):
        for file in files:
            if file in email_images:
                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                # print(filename,file_path)
                img = MIMEImage(open(file_path, 'rb').read())
                img.add_header('Content-Id', f'<{filename}>')
                msg.attach(img)

    msg.send()

def return_consumable(request, id):
    consumable = get_object_or_404(Consumable, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated consumable data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        option = data.get('return_by', 0)

        amount = data.get('amount', 0)

        if option == 'Pack size':
            tmp = int(consumable.pack_size_rem) + int(amount)
            if tmp <= consumable.pack_size:
                consumable.pack_size_rem = tmp
                log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} added to {consumable.name} pack')
            else:
                consumable.quantity = int(consumable.quantity) + int(tmp//consumable.pack_size)
                # print(int(tmp/consumable.pack_size))
                if tmp%consumable.pack_size == 0:
                    consumable.pack_size_rem = consumable.pack_size
                else:
                    consumable.pack_size_rem = tmp%consumable.pack_size

                log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{int(tmp/consumable.pack_size)} {consumable.name} added to  stock')
        else:
            consumable.quantity = int(consumable.quantity) + int(amount)
            log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} {consumable.name} added to  stock')
        
        # Save the changes
        # log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{amount} {consumable.name} added to  stock')
        consumable.save()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Consumable with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating consumable with ID {id}.'}, status=400)

def deleteConsumable(request,project_name,pk):
    try:
        project = get_object_or_404(Project, name=project_name)
        consumable = get_object_or_404(Consumable, project=project, id=pk)
        trash_consumable = TrashConsumable.objects.create(
            project=project,
            name=consumable.name,
            product_code=consumable.product_code,
            pack_size=consumable.pack_size,
            pack_size_rem=consumable.pack_size_rem,
            quantity=consumable.quantity,
            expiry_date=consumable.expiry_date,
            date_recorded=consumable.date_recorded,
            storage_location=consumable.storage_location,
            threshold_value=consumable.threshold_value
        )
        consumable.delete()
        log_entry = Log.objects.create(project=consumable.project,user=request.user,action=f'{consumable.name} deleted')
        return JsonResponse({'message': 'Consumable deleted successfully'}, status=200)

    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    except Consumable.DoesNotExist:
        return JsonResponse({'error': 'Consumable not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def deleteTrashConsumable(request,trash_consumable_id):
    trash_consumable = TrashConsumable.objects.get(id=trash_consumable_id)

    log_entry = Log.objects.create(project=trash_consumable.project,user=request.user,action=f'{trash_consumable.name} deleted from Trash')

    trash_consumable.delete()
    
    return redirect(f'/trash_consumables/{trash_consumable.project.name}')

def delete_all_consumables_in_trash(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)
    trashconsumables = TrashConsumable.objects.filter(project=project)
    trashconsumables.delete()
    log_entry = Log.objects.create(project=project,user=request.user,action=f'Consumables trash emptied')
    return JsonResponse({'message': 'All consumables in the trash have been deleted.'})

def restoreConsumable(request,project_name,trash_consumable_id):
    project = get_object_or_404(Project, name=project_name)
    trash_consumable = TrashConsumable.objects.get(id=trash_consumable_id)
    consumable = Consumable.objects.create(
            project=project,
            name=trash_consumable.name,
            pack_size=trash_consumable.pack_size,
            pack_size_rem=trash_consumable.pack_size_rem,
            product_code=trash_consumable.product_code,
            quantity=trash_consumable.quantity,
            expiry_date=trash_consumable.expiry_date,
            date_recorded=trash_consumable.date_recorded,
            threshold_value=trash_consumable.threshold_value,
            storage_location=trash_consumable.storage_location
        )
    log_entry = Log.objects.create(project=trash_consumable.project,user=request.user,action=f'{consumable.name} restored from Trash')
    trash_consumable.delete()
    return redirect(f'/trash_consumables/{project_name}/')


def export_consumable_csv(request,project_name):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="consumables.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Product Code', 'Pack Size','Quantity', 'Expiry Date', 'Date Created', 'Storage Location', 'Threshold Value'])

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    consumables = project.consumable_set.all()

    for consumable in consumables:
        writer.writerow([
            consumable.name,
            consumable.product_code,
            str(consumable.pack_size_rem) + '/' + str(consumable.pack_size),
            consumable.quantity,
            consumable.expiry_date,
            consumable.date_recorded,
            consumable.storage_location,
            consumable.threshold_value 
        ])

    return response

def export_consumable_excel(request,project_name):
    # Create a new Workbook object
    workbook = Workbook()

    # Get the default sheet
    sheet = workbook.active

    # Write headers to the sheet
    headers = ['Name', 'Product Code', 'Pack Size', 'Quantity', 'Expiry Date', 'Date Created', 'Storage Location', 'Threshold Value']
    sheet.append(headers)

    # Retrieve Consumable objects from the database
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    consumables = project.consumable_set.all()

    # Write Consumable data to the sheet
    for consumable in consumables:
        row_data = [
            consumable.name,
            consumable.product_code,
            str(consumable.pack_size_rem) + '/' + str(consumable.pack_size),
            consumable.quantity,
            consumable.expiry_date,
            consumable.date_recorded,
            consumable.storage_location,
            consumable.threshold_value  
        ]
        sheet.append(row_data)

    # Create a response object with the appropriate content type
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Set the file name for the response
    response['Content-Disposition'] = 'attachment; filename="consumables.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response

def export_consumable_txt(request, project_name):
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="consumables.txt"'

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    consumables = project.consumable_set.all()

    content = ''
    for consumable in consumables:
        content += f"Name: {consumable.name}\n"
        content += f"Product Code: {consumable.product_code}\n"
        content += f"Pack Size: {consumable.pack_size_rem}/{consumable.pack_size}\n"
        content += f"Quantity: {consumable.quantity}\n"
        content += f"Expiry Date: {consumable.expiry_date}\n"
        content += f"Date Created: {consumable.date_recorded}\n"
        content += f"Storage Location: {consumable.storage_location}\n"
        content += f"Threshold: {consumable.threshold_value}\n"
        content += "\n"

    response.write(content)

    return response



@login_required(login_url='login')
def reagents(request,project_name):
    # projects = Project.objects.all()
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)

    if project:
        projects = user_profile.managed_projects.all()
        # Retrieve the project object based on the provided project name
        

        # Retrieve all the reagents related to the project
        reagents = project.reagent_set.all()

        context = {'project': project, 'projects': projects,'reagents': reagents, 'user': user}
        return render(request, 'inventory/reagents.html', context)

def addReagent(request, project_name):
    try:
        if request.method == 'POST':
            # Retrieve the form data from the request
            project = Project.objects.get(name=project_name)
            name = request.POST.get('name')
            product_code = request.POST.get('product_code')
            pack_size = request.POST.get('pack_size')
            quantity = request.POST.get('quantity')
            expiry_date = request.POST.get('expiry_date')
            storage_location = request.POST.get('storage_location')
            threshold_value = request.POST.get('threshold_value')
            # Create a new Reagent instance associated with the active project
            reagent = Reagent.objects.create(project=project, name=name, product_code=product_code, pack_size=pack_size, pack_size_rem=pack_size, quantity=quantity, expiry_date=expiry_date, storage_location=storage_location, threshold_value=threshold_value)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{name} added to Reagents')
        
            return redirect(f'/reagents/{project_name}')
            # return JsonResponse({'message': 'Reagent created successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def dashboard_reagents(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    reagents = project.reagent_set.all()

    # Prepare data for Plotly.js
    names = []
    quantities = []
    for reagent in reagents:
        names.append(reagent.name)
        quantities.append(reagent.quantity)
    
    data = {'names': names, 'quantities': quantities}
    plot_data = json.dumps(data)

    # Render the template with the plot data
    return render(request, 'inventory/dashboard_reagents.html', {'plot_data': plot_data,'project': project, 'projects': projects,'reagents': reagents})

def trash_reagents(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    trash_reagents = project.trashreagent_set.all()
    context = {'project': project, 'projects': projects,'trash_reagents': trash_reagents}
    return render(request, 'inventory/trash_reagents.html', context)
    
def get_reagent_info(request, id):
    reagent = get_object_or_404(Reagent, id=id)
    
    # Prepare the data to be sent back as a JSON response
    data = {
        'name': reagent.name,
        'product_code': reagent.product_code,
        'pack_size': reagent.pack_size,
        'pack_size_rem': reagent.pack_size_rem,
        'quantity': reagent.quantity,
        'expiry_date': reagent.expiry_date,
        'date_recorded': reagent.date_recorded,
        'storage_location': reagent.storage_location,
        'threshold_value': reagent.threshold_value,
        
    }
    
    return JsonResponse(data)

def edit_reagent(request, id):
    reagent = get_object_or_404(Reagent, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated reagent data as JSON

        # Extract the data from the request body
        data = json.loads(request.body)

        # Update the reagent with the new data
        reagent.name = data.get('name', reagent.name)
        reagent.product_code = data.get('product_code', reagent.product_code)
        reagent.pack_size = data.get('pack_size', reagent.pack_size)
        reagent.quantity = data.get('quantity', reagent.quantity)
        reagent.expiry_date = data.get('expiry_date ', reagent.expiry_date )
        reagent.storage_location = data.get('storage_location', reagent.storage_location)
        reagent.threshold_value = data.get('threshold_value', reagent.threshold_value)
        # Update other fields accordingly
        log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{reagent.name} details edited')
        # Save the changes
        reagent.save()

        # Return a JSON response indicating success
        return JsonResponse({'message': f'Reagent with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating reagent with ID {id}.'}, status=400)

def retrieve_reagent(request, id):
    reagent = get_object_or_404(Reagent, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated reagent data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        option = data.get('retrieve_by', 0)

        amount = data.get('amount', 0)

        if option == 'Pack size':
            tmp = int(reagent.pack_size_rem) - int(amount)
            if tmp == 0:
                reagent.quantity = int(reagent.quantity) - 1
                reagent.pack_size_rem = reagent.pack_size
                log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'1 {reagent.name} taken from stock')
            elif tmp > 0:
                reagent.pack_size_rem = tmp
                log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} removed from {reagent.name} pack')
            else:
                if abs(tmp)%reagent.pack_size == 0:
                    reagent.quantity = int(reagent.quantity) - int(abs(tmp)/reagent.pack_size) - 1
                    reagent.pack_size_rem = reagent.pack_size
                    log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{int(abs(tmp)/reagent.pack_size) - 1} {reagent.name} taken from stock')
                else:
                    reagent.quantity = int(reagent.quantity) - int(abs(tmp)/reagent.pack_size) - 1
                    reagent.pack_size_rem = reagent.pack_size - abs(tmp)%reagent.pack_size
                    log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} removed from {reagent.name} pack')
                    
        else:
            reagent.quantity = int(reagent.quantity) - int(amount)
            log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} {reagent.name} taken from stock')

        # Save the changes
        # log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{quantity_to_subtract} {reagent.name} taken from stock')
        reagent.save()
        if reagent.quantity < reagent.threshold_value:
            email_thread = threading.Thread(target=send_reagent_notification, args=(reagent,))
            email_thread.start()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Reagent with ID {id} updated successfully.'})
        # return redirect(f'/reagents/{reagent.project.name}')

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating reagent with ID {id}.'}, status=400)

def send_reagent_notification(reagent):
    subject = 'Reagent Quantity Below Threshold'
    message = f"The quantity of {reagent.name} is below the threshold. Please take necessary action."
    recipient_list = [reagent.project.project_manager.email]  # Add the email address to send the notification

     # Render the HTML template as a string
    html_message = render_to_string('inventory/shortage_email_template.html', {'reagent': reagent})
    # send_mail(subject, message, 'settings.EMAIL_HOST_USER', recipient_list, fail_silently=False)
    msg = EmailMultiAlternatives(subject, html_message, 'settings.EMAIL_HOST_USER', recipient_list)

    msg.mixed_subtype = 'related'
    msg.attach_alternative(html_message, "text/html")
    email_images = ["Bell.png", "Logo_Orange.png", "Logo_White.png", "facebook2x.png", "instagram2x.png", "linkedin2x.png", "twitter2x.png"]
    for root, dirs, files in os.walk('C:/Users/HP/Desktop/inventory_system/static/images/'):
        for file in files:
            if file in email_images:
                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                # print(filename,file_path)
                img = MIMEImage(open(file_path, 'rb').read())
                img.add_header('Content-Id', f'<{filename}>')
                msg.attach(img)

    msg.send()

def return_reagent(request, id):
    reagent = get_object_or_404(Reagent, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated reagent data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        option = data.get('return_by', 0)

        amount = data.get('amount', 0)

        if option == 'Pack size':
            tmp = int(reagent.pack_size_rem) + int(amount)
            if tmp <= reagent.pack_size:
                reagent.pack_size_rem = tmp
                log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} added to {reagent.name} pack')
            else:
                reagent.quantity = int(reagent.quantity) + int(tmp//reagent.pack_size)
                # print(int(tmp/reagent.pack_size))
                if tmp%reagent.pack_size == 0:
                    reagent.pack_size_rem = reagent.pack_size
                else:
                    reagent.pack_size_rem = tmp%reagent.pack_size

                log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{int(tmp/reagent.pack_size)} {reagent.name} added to  stock')
        else:
            reagent.quantity = int(reagent.quantity) + int(amount)
            log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} {reagent.name} added to  stock')
        
        # Save the changes
        # log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{amount} {reagent.name} added to  stock')
        reagent.save()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Reagent with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating reagent with ID {id}.'}, status=400)

def deleteReagent(request,project_name,pk):
    try:
        project = get_object_or_404(Project, name=project_name)
        reagent = get_object_or_404(Reagent, project=project, id=pk)
        trash_reagent = TrashReagent.objects.create(
            project=project,
            name=reagent.name,
            product_code=reagent.product_code,
            pack_size=reagent.pack_size,
            pack_size_rem=reagent.pack_size_rem,
            quantity=reagent.quantity,
            expiry_date=reagent.expiry_date,
            date_recorded=reagent.date_recorded,
            storage_location=reagent.storage_location,
            threshold_value=reagent.threshold_value
        )
        reagent.delete()
        log_entry = Log.objects.create(project=reagent.project,user=request.user,action=f'{reagent.name} deleted')
        return JsonResponse({'message': 'Reagent deleted successfully'}, status=200)

    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    except Reagent.DoesNotExist:
        return JsonResponse({'error': 'Reagent not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def deleteTrashReagent(request,trash_reagent_id):
    trash_reagent = TrashReagent.objects.get(id=trash_reagent_id)

    log_entry = Log.objects.create(project=trash_reagent.project,user=request.user,action=f'{trash_reagent.name} deleted from Trash')

    trash_reagent.delete()
    
    return redirect(f'/trash_reagents/{trash_reagent.project.name}')

def delete_all_reagents_in_trash(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)
    trashreagents = TrashReagent.objects.filter(project=project)
    trashreagents.delete()
    log_entry = Log.objects.create(project=project,user=request.user,action=f'Reagents trash emptied')
    return JsonResponse({'message': 'All reagents in the trash have been deleted.'})

def restoreReagent(request,project_name,trash_reagent_id):
    project = get_object_or_404(Project, name=project_name)
    trash_reagent = TrashReagent.objects.get(id=trash_reagent_id)
    reagent = Reagent.objects.create(
            project=project,
            name=trash_reagent.name,
            pack_size=trash_reagent.pack_size,
            pack_size_rem=trash_reagent.pack_size_rem,
            product_code=trash_reagent.product_code,
            quantity=trash_reagent.quantity,
            expiry_date=trash_reagent.expiry_date,
            date_recorded=trash_reagent.date_recorded,
            threshold_value=trash_reagent.threshold_value,
            storage_location=trash_reagent.storage_location
        )
    log_entry = Log.objects.create(project=trash_reagent.project,user=request.user,action=f'{reagent.name} restored from Trash')
    trash_reagent.delete()
    return redirect(f'/trash_reagents/{project_name}/')


def export_reagent_csv(request,project_name):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reagents.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Product Code', 'Pack Size','Quantity', 'Expiry Date', 'Date Created', 'Storage Location', 'Threshold Value'])

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    reagents = project.reagent_set.all()

    for reagent in reagents:
        writer.writerow([
            reagent.name,
            reagent.product_code,
            str(reagent.pack_size_rem) + '/' + str(reagent.pack_size),
            reagent.quantity,
            reagent.expiry_date,
            reagent.date_recorded,
            reagent.storage_location,
            reagent.threshold_value 
        ])

    return response

def export_reagent_excel(request,project_name):
    # Create a new Workbook object
    workbook = Workbook()

    # Get the default sheet
    sheet = workbook.active

    # Write headers to the sheet
    headers = ['Name', 'Product Code', 'Pack Size', 'Quantity', 'Expiry Date', 'Date Created', 'Storage Location', 'Threshold Value']
    sheet.append(headers)

    # Retrieve Reagent objects from the database
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    reagents = project.reagent_set.all()

    # Write Reagent data to the sheet
    for reagent in reagents:
        row_data = [
            reagent.name,
            reagent.product_code,
            str(reagent.pack_size_rem) + '/' + str(reagent.pack_size),
            reagent.quantity,
            reagent.expiry_date,
            reagent.date_recorded,
            reagent.storage_location,
            reagent.threshold_value  
        ]
        sheet.append(row_data)

    # Create a response object with the appropriate content type
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Set the file name for the response
    response['Content-Disposition'] = 'attachment; filename="reagents.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response

def export_reagent_txt(request, project_name):
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="reagents.txt"'

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    reagents = project.reagent_set.all()

    content = ''
    for reagent in reagents:
        content += f"Name: {reagent.name}\n"
        content += f"Product Code: {reagent.product_code}\n"
        content += f"Pack Size: {reagent.pack_size_rem}/{reagent.pack_size}\n"
        content += f"Quantity: {reagent.quantity}\n"
        content += f"Expiry Date: {reagent.expiry_date}\n"
        content += f"Date Created: {reagent.date_recorded}\n"
        content += f"Storage Location: {reagent.storage_location}\n"
        content += f"Threshold: {reagent.threshold_value}\n"
        content += "\n"

    response.write(content)

    return response





@login_required(login_url='login')
def equipment_(request,project_name):
    # projects = Project.objects.all()
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)

    if project:
        projects = user_profile.managed_projects.all()
        # Retrieve the project object based on the provided project name
        

        # Retrieve all the equipment_ related to the project
        equipment_ = project.equipment_set.all()

        context = {'project': project, 'projects': projects,'equipment_': equipment_, 'user': user}
        return render(request, 'inventory/equipment_.html', context)

def addEquipment(request, project_name):
    try:
        if request.method == 'POST':
            # Retrieve the form data from the request
            project = Project.objects.get(name=project_name)
            name = request.POST.get('name')
            equip_id = request.POST.get('equip_id')
            serial_num = request.POST.get('serial_num')
            quantity = request.POST.get('quantity')
            status = request.POST.get('status')
            service_contract_start = request.POST.get('service_contract_start')
            service_contract_end = request.POST.get('service_contract_end')
            donated_by = request.POST.get('donated_by')
            storage_location = request.POST.get('storage_location')
            
            # Create a new Equipment instance associated with the active project
            equipment = Equipment.objects.create(project=project, name=name, equip_id=equip_id, serial_num=serial_num, quantity=quantity, status=status, service_contract_start=service_contract_start, service_contract_end=service_contract_end, donated_by=donated_by, storage_location=storage_location)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{name} added to Equipment')
        
            return redirect(f'/equipment_/{project_name}')
            # return JsonResponse({'message': 'Equipment created successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def dashboard_equipment_(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    equipment_ = project.equipment_set.all()

    # Prepare data for Plotly.js
    names = []
    quantities = []
    for equipment in equipment_:
        names.append(equipment.name)
        quantities.append(equipment.quantity)
    
    data = {'names': names, 'quantities': quantities}
    plot_data = json.dumps(data)

    # Render the template with the plot data
    return render(request, 'inventory/dashboard_equipment_.html', {'plot_data': plot_data,'project': project, 'projects': projects,'equipment_': equipment_})

def trash_equipment_(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    trash_equipment_ = project.trashequipment_set.all()
    context = {'project': project, 'projects': projects,'trash_equipment_': trash_equipment_}
    return render(request, 'inventory/trash_equipment_.html', context)
    
def get_equipment_info(request, id):
    equipment = get_object_or_404(Equipment, id=id)
    
    # Prepare the data to be sent back as a JSON response
    data = {
        'name' : equipment.name,
        'equip_id' : equipment.equip_id,
        'serial_num' : equipment.serial_num,
        'quantity' : equipment.quantity,
        'status' : equipment.status,
        'service_contract_start' : equipment.service_contract_start,
        'service_contract_end' : equipment.service_contract_end,
        'donated_by' : equipment.donated_by,
        'storage_location' : equipment.storage_location,
    }
    
    return JsonResponse(data)

def send_equipment_fault_notification(equipment):
    subject = 'Faulty Equipment'
    project_manager_mail = [equipment.project.project_manager.email]  # Add the email address to send the notification
    project_editors = equipment.project.project_editors.all()
    project_members = equipment.project.project_members.all()

    # Get their emails
    editor_emails = [editor.email for editor in project_editors]
    member_emails = [member.email for member in project_members]

    recipient_list = project_manager_mail + editor_emails + member_emails
    print(recipient_list)

     # Render the HTML template as a string
    html_message = render_to_string('inventory/non_functional_equipment_email_template.html', {'equipment': equipment})
    # send_mail(subject, message, 'settings.EMAIL_HOST_USER', recipient_list, fail_silently=False)
    msg = EmailMultiAlternatives(subject, html_message, 'settings.EMAIL_HOST_USER', recipient_list)

    msg.mixed_subtype = 'related'
    msg.attach_alternative(html_message, "text/html")
    email_images = ["Bell.png", "Logo_Orange.png", "Logo_White.png", "facebook2x.png", "instagram2x.png", "linkedin2x.png", "twitter2x.png"]
    for root, dirs, files in os.walk('C:/Users/HP/Desktop/inventory_system/static/images/'):
        for file in files:
            if file in email_images:
                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                # print(filename,file_path)
                img = MIMEImage(open(file_path, 'rb').read())
                img.add_header('Content-Id', f'<{filename}>')
                msg.attach(img)

    msg.send()

def edit_equipment(request, id):
    equipment = get_object_or_404(Equipment, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated equipment data as JSON

        # Extract the data from the request body
        data = json.loads(request.body)

        # Update the equipment with the new data
        equipment.name = data.get('name', equipment.name)
        equipment.equip_id = data.get('equip_id', equipment.equip_id)
        equipment.serial_num = data.get('serial_num', equipment.serial_num)
        equipment.quantity = data.get('quantity', equipment.quantity)
        equipment.status = data.get('status', equipment.status)
        equipment.service_contract_start = data.get('service_contract_start', equipment.service_contract_start)
        equipment.service_contract_end = data.get('service_contract_end', equipment.service_contract_end)
        equipment.donated_by = data.get('donated_by', equipment.donated_by)
        equipment.storage_location = data.get('storage_location', equipment.storage_location)

        if equipment.status == "Faulty":
            email_thread = threading.Thread(target=send_equipment_fault_notification, args=(equipment,))
            email_thread.start()

        # Update other fields accordingly
        log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{equipment.name} details edited')
        # Save the changes
        equipment.save()

        # Return a JSON response indicating success
        return JsonResponse({'message': f'Equipment with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating equipment with ID {id}.'}, status=400)

def retrieve_equipment(request, id):
    equipment = get_object_or_404(Equipment, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated equipment data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        quantity = data.get('quantity', 0)

        equipment.quantity = int(equipment.quantity) - int(quantity)
        log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{quantity} {equipment.name} taken from stock')

        # Save the changes
        # log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{quantity_to_subtract} {equipment.name} taken from stock')
        equipment.save()
        return JsonResponse({'message': f'Equipment with ID {id} updated successfully.'})
        # return redirect(f'/equipment_/{equipment.project.name}')

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating equipment with ID {id}.'}, status=400)

def return_equipment(request, id):
    equipment = get_object_or_404(Equipment, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated equipment data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        quantity = data.get('quantity', 0)

        equipment.quantity = int(equipment.quantity) + int(quantity)
        log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{quantity} {equipment.name} added to  stock')
        
        # Save the changes
        # log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{amount} {equipment.name} added to  stock')
        equipment.save()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Equipment with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating equipment with ID {id}.'}, status=400)

def deleteEquipment(request,project_name,pk):
    try:
        project = get_object_or_404(Project, name=project_name)
        equipment = get_object_or_404(Equipment, project=project, id=pk)
        trash_equipment = TrashEquipment.objects.create(
            project=project,
            name=equipment.name,
            equip_id=equipment.equip_id,
            serial_num=equipment.serial_num,
            quantity=equipment.quantity,
            status=equipment.status,
            service_contract_start=equipment.service_contract_start,
            service_contract_end=equipment.service_contract_end,
            date_recorded=equipment.date_recorded,
            donated_by=equipment.donated_by,
            storage_location=equipment.storage_location
        )
        equipment.delete()
        log_entry = Log.objects.create(project=equipment.project,user=request.user,action=f'{equipment.name} deleted')
        return JsonResponse({'message': 'Equipment deleted successfully'}, status=200)

    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    except Equipment.DoesNotExist:
        return JsonResponse({'error': 'Equipment not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def deleteTrashEquipment(request,trash_equipment_id):
    trash_equipment = TrashEquipment.objects.get(id=trash_equipment_id)

    log_entry = Log.objects.create(project=trash_equipment.project,user=request.user,action=f'{trash_equipment.name} deleted from Trash')

    trash_equipment.delete()
    
    return redirect(f'/trash_equipment_/{trash_equipment.project.name}')

def delete_all_equipment__in_trash(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)
    trashequipment_ = TrashEquipment.objects.filter(project=project)
    trashequipment_.delete()
    log_entry = Log.objects.create(project=project,user=request.user,action=f'Equipment trash emptied')
    return JsonResponse({'message': 'All equipment_ in the trash have been deleted.'})

def restoreEquipment(request,project_name,trash_equipment_id):
    project = get_object_or_404(Project, name=project_name)
    trash_equipment = TrashEquipment.objects.get(id=trash_equipment_id)
    equipment = Equipment.objects.create(
            project=project,
            name=trash_equipment.name,
            equip_id=trash_equipment.equip_id,
            serial_num=trash_equipment.serial_num,
            quantity=trash_equipment.quantity,
            status=trash_equipment.status,
            service_contract_start=trash_equipment.service_contract_start,
            service_contract_end=trash_equipment.service_contract_end,
            date_recorded=trash_equipment.date_recorded,
            donated_by=trash_equipment.donated_by,
            storage_location=trash_equipment.storage_location
        )
    log_entry = Log.objects.create(project=trash_equipment.project,user=request.user,action=f'{equipment.name} restored from Trash')
    trash_equipment.delete()
    return redirect(f'/trash_equipment_/{project_name}/')


def export_equipment_csv(request,project_name):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="equipment_.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'ID', 'Serial Number','Quantity', 'Status', 'Service Contract Start', 'Service Contract End', 'Donated', 'Storage Location'])

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    equipment_ = project.equipment_set.all()

    for equipment in equipment_:
        writer.writerow([
            equipment.name,
            equipment.equip_id,
            equipment.serial_num,
            equipment.quantity,
            equipment.status,
            equipment.service_contract_start,
            equipment.service_contract_end,
            equipment.donated_by,
            equipment.storage_location 
        ])

    return response

def export_equipment_excel(request,project_name):
    # Create a new Workbook object
    workbook = Workbook()

    # Get the default sheet
    sheet = workbook.active

    # Write headers to the sheet
    headers = ['Name', 'ID', 'Serial Number','Quantity', 'Status', 'Service Contract Start', 'Service Contract End', 'Donated', 'Storage Location']
    sheet.append(headers)

    # Retrieve Equipment objects from the database
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    equipment_ = project.equipment_set.all()

    # Write Equipment data to the sheet
    for equipment in equipment_:
        row_data = [
            equipment.name,
            equipment.equip_id,
            equipment.serial_num,
            equipment.quantity,
            equipment.status,
            equipment.service_contract_start,
            equipment.service_contract_end,
            equipment.donated_by,
            equipment.storage_location  
        ]
        sheet.append(row_data)

    # Create a response object with the appropriate content type
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Set the file name for the response
    response['Content-Disposition'] = 'attachment; filename="equipment_.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response

def export_equipment_txt(request, project_name):
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="equipment_.txt"'

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    equipment_ = project.equipment_set.all()
    content = ''
    for equipment in equipment_:
        content += f"Name: {equipment.name}\n"
        content += f"ID: {equipment.equip_id}\n"
        content += f"Serial Number: {equipment.serial_num}\n"
        content += f"Quantity: {equipment.quantity}\n"
        content += f"Status: {equipment.status}\n"
        content += f"Service Contract Start: {equipment.service_contract_start}\n"
        content += f"Service Contract End: {equipment.service_contract_end}\n"
        content += f"Donated By: {equipment.donated_by}\n"
        content += f"Storage Location: {equipment.storage_location}\n"
        content += "\n"

    response.write(content)

    return response










@login_required(login_url='login')
def samples(request,project_name):
    # projects = Project.objects.all()
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)

    if project:
        projects = user_profile.managed_projects.all()
        # Retrieve the project object based on the provided project name
        

        # Retrieve all the samples related to the project
        samples = project.sample_set.all()

        context = {'project': project, 'projects': projects,'samples': samples, 'user': user}
        return render(request, 'inventory/samples.html', context)

def addSample(request, project_name):
    try:
        if request.method == 'POST':
            # Retrieve the form data from the request
            project = Project.objects.get(name=project_name)
            sample_id = request.POST.get('sample_id')
            sample_type = request.POST.get('sample_type')
            description = request.POST.get('description')
            country = request.POST.get('country')
            volume = request.POST.get('volume')
            well_id = request.POST.get('well_id')
            storage_location = request.POST.get('storage_location')
            threshold_value = request.POST.get('threshold_value')
            # Create a new Sample instance associated with the active project
            sample = Sample.objects.create(project=project, sample_id=sample_id, sample_type=sample_type, description=description, country=country, volume=volume, well_id=well_id, storage_location=storage_location, threshold_value=threshold_value)
            log_entry = Log.objects.create(project=project,user=request.user,action=f'{sample_id} added to Samples')
        
            return redirect(f'/samples/{project_name}')
            # return JsonResponse({'message': 'Sample created successfully'}, status=200)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
def dashboard_samples(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    samples = project.sample_set.all()

    # Prepare data for Plotly.js
    ids = []
    volumes = []
    for sample in samples:
        ids.append(sample.sample_id)
        volumes.append(sample.volume)
    
    data = {'ids': ids, 'volumes': volumes}
    plot_data = json.dumps(data)

    # Render the template with the plot data
    return render(request, 'inventory/dashboard_samples.html', {'plot_data': plot_data,'project': project, 'projects': projects,'samples': samples})

def trash_samples(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    trash_samples = project.trashsample_set.all()
    context = {'project': project, 'projects': projects,'trash_samples': trash_samples}
    return render(request, 'inventory/trash_samples.html', context)
    
def get_sample_info(request, id):
    sample = get_object_or_404(Sample, id=id)
    
    # Prepare the data to be sent back as a JSON response
    data = {
        'sample_id': sample.sample_id,
        'sample_type': sample.sample_type,
        'description': sample.description,
        'country': sample.country,
        'volume': sample.volume,
        'well_id': sample.well_id,
        'date_recorded': sample.date_recorded,
        'storage_location': sample.storage_location,
        'threshold_value': sample.threshold_value,
        
    }
    
    return JsonResponse(data)

def edit_sample(request, id):
    sample = get_object_or_404(Sample, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated sample data as JSON

        # Extract the data from the request body
        data = json.loads(request.body)

        # Update the sample with the new data
        sample.sample_id = data.get('sample_id', sample.sample_id)
        sample.sample_type = data.get('sample_type', sample.sample_type)
        sample.description = data.get('description', sample.description)
        sample.country = data.get('country', sample.country)
        sample.volume = data.get('volume', sample.volume)
        sample.well_id = data.get('well_id', sample.well_id)
        sample.storage_location = data.get('storage_location', sample.storage_location)
        sample.threshold_value = data.get('threshold_value', sample.threshold_value)
        # Update other fields accordingly
        log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{sample.sample_id} details edited')
        # Save the changes
        sample.save()

        # Return a JSON response indicating success
        return JsonResponse({'message': f'Sample with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating sample with ID {id}.'}, status=400)

def retrieve_sample(request, id):
    sample = get_object_or_404(Sample, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated sample data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        amount = data.get('amount', 0)

        sample.volume = int(sample.volume) - int(amount)
        log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{amount} {sample.sample_id} taken from stock')

        # Save the changes
        # log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{quantity_to_subtract} {sample.sample_id} taken from stock')
        sample.save()
        if sample.volume < sample.threshold_value:
            email_thread = threading.Thread(target=send_sample_notification, args=(sample,))
            email_thread.start()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Sample with ID {id} updated successfully.'})
        # return redirect(f'/samples/{sample.project.name}')

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating sample with ID {id}.'}, status=400)

def send_sample_notification(sample):
    subject = 'Sample Volume Below Threshold'
    message = f"The volume of {sample.sample_id} is below the threshold. Please take necessary action."
    recipient_list = [sample.project.project_manager.email]  # Add the email address to send the notification

     # Render the HTML template as a string
    html_message = render_to_string('inventory/shortage_email_template.html', {'sample': sample})
    # send_mail(subject, message, 'settings.EMAIL_HOST_USER', recipient_list, fail_silently=False)
    msg = EmailMultiAlternatives(subject, html_message, 'settings.EMAIL_HOST_USER', recipient_list)

    msg.mixed_subtype = 'related'
    msg.attach_alternative(html_message, "text/html")
    email_images = ["Bell.png", "Logo_Orange.png", "Logo_White.png", "facebook2x.png", "instagram2x.png", "linkedin2x.png", "twitter2x.png"]
    for root, dirs, files in os.walk('C:/Users/HP/Desktop/inventory_system/static/images/'):
        for file in files:
            if file in email_images:
                file_path = os.path.join(root, file)
                filename = os.path.splitext(file)[0]
                # print(filename,file_path)
                img = MIMEImage(open(file_path, 'rb').read())
                img.add_header('Content-Id', f'<{filename}>')
                msg.attach(img)

    msg.send()

def return_sample(request, id):
    sample = get_object_or_404(Sample, id=id)

    if request.method == 'PUT':
        # Assuming the request body contains the updated sample data as JSON
        # Extract the data from the request body
        data = json.loads(request.body)

        amount = data.get('amount', 0)

        sample.volume = int(sample.volume) + int(amount)

        log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{amount} {sample.sample_id} added to  stock')
        
        # Save the changes
        # log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{amount} {sample.sample_id} added to  stock')
        sample.save()
        # Return a JSON response indicating success
        return JsonResponse({'message': f'Sample with ID {id} updated successfully.'})

    # Return a JSON response indicating failure
    return JsonResponse({'error': f'Error updating sample with ID {id}.'}, status=400)

def deleteSample(request,project_name,pk):
    try:
        project = get_object_or_404(Project, name=project_name)
        sample = get_object_or_404(Sample, project=project, id=pk)
        trash_sample = TrashSample.objects.create(
            project = project,
            sample_id = sample.sample_id,
            sample_type = sample.sample_type,
            description = sample.description,
            country = sample.country,
            volume = sample.volume,
            well_id = sample.well_id,
            date_recorded=sample.date_recorded,
            storage_location = sample.storage_location,
            threshold_value = sample.threshold_value
        )
        sample.delete()
        log_entry = Log.objects.create(project=sample.project,user=request.user,action=f'{sample.sample_id} deleted')
        return JsonResponse({'message': 'Sample deleted successfully'}, status=200)

    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)

    except Sample.DoesNotExist:
        return JsonResponse({'error': 'Sample not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def deleteTrashSample(request,trash_sample_id):
    trash_sample = TrashSample.objects.get(id=trash_sample_id)

    log_entry = Log.objects.create(project=trash_sample.project,user=request.user,action=f'{trash_sample.sample_id} deleted from Trash')

    trash_sample.delete()
    
    return redirect(f'/trash_samples/{trash_sample.project.name}')

def delete_all_samples_in_trash(request,project_name):
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    project = user_profile.managed_projects.get(name=project_name)
    trashsamples = TrashSample.objects.filter(project=project)
    trashsamples.delete()
    log_entry = Log.objects.create(project=project,user=request.user,action=f'Samples trash emptied')
    return JsonResponse({'message': 'All samples in the trash have been deleted.'})

def restoreSample(request,project_name,trash_sample_id):
    project = get_object_or_404(Project, name=project_name)
    trash_sample = TrashSample.objects.get(id=trash_sample_id)
    sample = Sample.objects.create(
            project = project,
            sample_id = trash_sample.sample_id,
            sample_type = trash_sample.sample_type,
            description = trash_sample.description,
            country = trash_sample.country,
            volume = trash_sample.volume,
            well_id = trash_sample.well_id,
            date_recorded=trash_sample.date_recorded,
            storage_location = trash_sample.storage_location,
            threshold_value = trash_sample.threshold_value
        )
    log_entry = Log.objects.create(project=trash_sample.project,user=request.user,action=f'{sample.sample_id} restored from Trash')
    trash_sample.delete()
    return redirect(f'/trash_samples/{project_name}/')


def export_sample_csv(request,project_name):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="samples.csv"'

    writer = csv.writer(response)
    writer.writerow(['Sample ID', 'Type', 'Description','Country', 'Volume', 'Well ID', 'Date Recorded','Storage Location', 'Threshold Value'])

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    samples = project.sample_set.all()

    for sample in samples:
        writer.writerow([
            sample.sample_id,
            sample.sample_type,
            sample.description,
            sample.country,
            sample.volume,
            sample.well_id,
            sample.date_recorded,
            sample.storage_location,
            sample.threshold_value 
        ])

    return response

def export_sample_excel(request,project_name):
    # Create a new Workbook object
    workbook = Workbook()

    # Get the default sheet
    sheet = workbook.active

    # Write headers to the sheet
    headers = ['Sample ID', 'Type', 'Description','Country', 'Volume', 'Well ID', 'Date Recorded','Storage Location', 'Threshold Value']
    sheet.append(headers)

    # Retrieve Sample objects from the database
    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    samples = project.sample_set.all()

    # Write Sample data to the sheet
    for sample in samples:
        row_data = [
            sample.sample_id,
            sample.sample_type,
            sample.description,
            sample.country,
            sample.volume,
            sample.well_id,
            sample.date_recorded,
            sample.storage_location,
            sample.threshold_value 
        ]
        sheet.append(row_data)

    # Create a response object with the appropriate content type
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Set the file name for the response
    response['Content-Disposition'] = 'attachment; filename="samples.xlsx"'

    # Save the workbook to the response
    workbook.save(response)

    return response

def export_sample_txt(request, project_name):
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="samples.txt"'

    user = request.user
    user_profile = UserProfile.objects.get(user=user)
    projects = user_profile.managed_projects.all()
    project = user_profile.managed_projects.get(name=project_name)
    samples = project.sample_set.all()

    content = ''
    for sample in samples:
        content += f"Sample ID: {sample.sample_id}\n"
        content += f"Type: {sample.sample_type}\n"
        content += f"Description: {sample.description}\n"
        content += f"Country: {sample.country}\n"
        content += f"Volume: {sample.volume}\n"
        content += f"Well ID: {sample.well_id}\n"
        content += f"Date Recorded: {sample.date_recorded}\n"
        content += f"Storage Location: {sample.storage_location}\n"
        content += f"Threshold: {sample.threshold_value}\n"
        content += "\n"

    response.write(content)

    return response