# forms.py
from django import forms
from django.utils import timezone
from .models import UserApplication, Project, Consumable, Reagent, MSDSFile
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .utils.msds_validation import validate_file_size
import random
import string
import uuid


# Centralized email validation
def validate_noguchi_email(email):
    if not email.endswith("@noguchi.ug.edu.gh"):
        raise ValidationError("Only Noguchi's email domains are allowed.")


# Centralized username generation
def generate_unique_username(first_name, last_name):
    base = f"{first_name}_{last_name}".lower()
    for _ in range(100):  # Max 100 attempts
        random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        username = f"{base}_{random_str}"
        if not User.objects.filter(username=username).exists():
            return username
    # Fallback to UUID if too many collisions
    return f"{base}_{uuid.uuid4().hex[:8]}"


class ConsumableForm(forms.ModelForm):
    class Meta:
        model = Consumable
        fields = ['name', 'product_code', 'pack_count', 'expiry_date', 'storage_location', 'threshold_value']

class ReagentForm(forms.ModelForm):
    class Meta:
        model = Reagent
        fields = [
            'name', 'product_code', 'items_per_pack', 'pack_count',
            'expiry_date', 'storage_location', 'cold_storage',
            'oem_temperature', 'temperature_unit', 'vendor',
            'country_of_origin', 'hazard_level', 'threshold_value', 'notes'
        ]
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'min': timezone.now().date()}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise forms.ValidationError("Expiry date cannot be in the past")
        return expiry_date

    def clean_hazard_level(self):
        hazard_level = self.cleaned_data.get('hazard_level')
        if hazard_level is not None and (hazard_level < 0 or hazard_level > 4):
            raise forms.ValidationError("Hazard level must be between 0 and 4")
        return hazard_level

    def clean_items_per_pack(self):
        items_per_pack = self.cleaned_data.get('items_per_pack')
        if items_per_pack <= 0:
            raise forms.ValidationError("Items per pack must be positive")
        return items_per_pack


class UserApplicationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_image'].widget.attrs.update({'data-preserve-file': 'true'})

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if UserApplication.objects.filter(email=email).exists():
            raise ValidationError('This email is already in use. Please use a different email.')

        validate_noguchi_email(email)

        return email

    class Meta:
        model = UserApplication
        fields = ['first_name', 'last_name', 'email', 'workplace', 'department', 'id_image']


class ProjectManagerSignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    project_name = forms.CharField(max_length=255)

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'project_name', 'password1', 'password2', )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)  # Get the request object from kwargs
        super().__init__(*args, **kwargs)

    def clean_project_name(self):
        project_name = self.cleaned_data['project_name']
        if Project.objects.filter(name=project_name).exists():
            raise forms.ValidationError('Project name already exists!')
        return project_name

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already in use. Please use a different email.')
        validate_noguchi_email(email)
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = generate_unique_username(
                self.cleaned_data["first_name"],
                self.cleaned_data["last_name"]
        )
        if commit:
            user.save()
        return user


class EditorMemberSignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Required. Enter a valid email address.')
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    # pm_email = forms.EmailField(max_length=254, help_text='Required. Enter a valid email address.')

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)  # Get the request object from kwargs
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already in use. Please use a different email.')

        validate_noguchi_email(email)

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = generate_unique_username(
                self.cleaned_data["first_name"],
                self.cleaned_data["last_name"]
        )
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)


class NewProjectForm(forms.Form):
    project_name = forms.CharField(max_length=255)

    def clean_project_name(self):
        project_name = self.cleaned_data['project_name']
        if Project.objects.filter(name=project_name).exists():
            raise ValidationError("Project name already exists.")
        return project_name


class MSDSUploadForm(forms.Form):
    msds_file = forms.FileField(
            label='MSDS File',
            help_text='Upload Material Safety Data Sheet (PDF only, max 5MB)',
            widget=forms.FileInput(attrs={'accept': '.pdf'})
    )

    def clean_file(self):
        msds_file = self.cleaned_data.get('msds_file')

        if not msds_file:
            return msds_file

        # Validate file size
        validate_file_size(msds_file)

        # Validate file type
        if not msds_file.name.lower().endswith('.pdf'):
            raise forms.ValidationError("Only PDF files are allowed")

        return file
