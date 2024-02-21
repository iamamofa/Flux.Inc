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

class ConsumableForm(forms.ModelForm):
    class Meta:
        model = Consumable
        fields = ['name', 'product_code', 'quantity', 'expiry_date', 'storage_location', 'threshold_value']

class ReagentForm(forms.ModelForm):
    class Meta:
        model = Reagent
        fields = '__all__'

class UserApplicationForm(forms.ModelForm):
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
            messages.error(self.request, 'Project name already exists. Please choose a different name.')
            raise forms.ValidationError('')  # Empty validation error to prevent form submission
        return project_name
    
    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            messages.error(self.request, 'This email is already in use. Please choose a different email.')
            raise forms.ValidationError('')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        user.username = f'{self.cleaned_data["first_name"]}_{self.cleaned_data["last_name"]}_{random_string}'
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
            messages.error(self.request, 'This email is already in use. Please choose a different email.')
            raise forms.ValidationError('')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        user.username = f'{self.cleaned_data["first_name"]}_{self.cleaned_data["last_name"]}_{random_string}'
        if commit:
            user.save()
        return user

class LoginForm(forms.Form):
    email = forms.EmailField(label='Email', max_length=254)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)

class NewProjectForm(forms.Form):
    project_name = forms.CharField(max_length=255)