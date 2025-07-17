# forms.py
from django import forms
from .models import *
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import AuthenticationForm
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
        fields = ['name', 'product_code', 'quantity', 'expiry_date', 'storage_location', 'threshold_value']

class ReagentForm(forms.ModelForm):
    class Meta:
        model = Reagent
        fields = '__all__'

class UserApplicationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_image'].widget.attrs.update({'data-preserve-file': 'true'})

    def clean_email(self):
        email = self.cleaned_data.get('email')

        if User.objects.filter(email=email).exists():
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
            # messages.error(self.request, 'Project name already exists. Kindly provide a different name.')
            raise forms.ValidationError('Project name already exists. Kindly provide a different name.')
        return project_name

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            # messages.error(self.request, 'This email is already in use. Please choose a different email.')
            raise forms.ValidationError('This email is already in use. Please use a different email.')
        validate_noguchi_email(email)
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        # user.username = f'{self.cleaned_data["first_name"]}_{self.cleaned_data["last_name"]}_{random_string}'
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
            # messages.error(self.request, 'This email is already in use. Please choose a different email.')
            raise forms.ValidationError('This email is already in use. Please use a different email.')
        validate_noguchi_email(email)
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        # user.username = f'{self.cleaned_data["first_name"]}_{self.cleaned_data["last_name"]}_{random_string}'
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
