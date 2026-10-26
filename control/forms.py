from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q
from inventory.models import UserProfile
from .models import Department, PortalSettings

User = get_user_model()


class StyledFormMixin:
    def style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'checkbox'
            else:
                field.widget.attrs['class'] = 'field-control'


class UserForm(StyledFormMixin, forms.ModelForm):
    department = forms.ChoiceField(required=False, choices=[])
    password1 = forms.CharField(label='Temporary password', widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, creating=False, **kwargs):
        self.creating = creating
        super().__init__(*args, **kwargs)
        department_names = list(Department.objects.filter(is_active=True).order_by('name').values_list('name', flat=True))
        old_department = ''
        if self.instance.pk:
            profile = UserProfile.objects.filter(user=self.instance).first()
            old_department = profile.department if profile else ''
        if old_department and old_department not in department_names:
            department_names.append(old_department)  # Retain assignments to inactive/legacy departments.
        self.fields['department'].choices = [('', 'Unassigned')] + [(d, d) for d in department_names]
        if self.instance.pk:
            self.fields['department'].initial = old_department
            self.fields.pop('password1')
            self.fields.pop('password2')
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True
        self.style_fields()

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if not email:
            raise ValidationError('An email address is required for account access.')
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This email address already belongs to another account.')
        return email

    def clean(self):
        cleaned = super().clean()
        if not self.instance.pk:
            password = cleaned.get('password1')
            if password != cleaned.get('password2'):
                self.add_error('password2', 'Passwords do not match.')
            if password:
                try:
                    validate_password(password, user=self.instance)
                except ValidationError as exc:
                    self.add_error('password1', exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if not user.pk:
            user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.department = self.cleaned_data.get('department', '').strip()
            profile.save(update_fields=['department', 'updated_at'])
        return user


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code', 'head', 'description', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['head'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.style_fields()


class SettingsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PortalSettings
        fields = ['institution_name', 'support_email', 'currency', 'date_format']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_currency(self):
        currency = self.cleaned_data['currency'].strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValidationError('Enter a three-letter currency code such as GHS.')
        return currency


class GroupForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {'permissions': forms.CheckboxSelectMultiple}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['permissions'].queryset = self.fields['permissions'].queryset.order_by('content_type__app_label', 'codename')
        self.style_fields()
