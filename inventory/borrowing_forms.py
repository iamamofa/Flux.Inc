"""Validation for the manager-to-manager stock exchange."""

from django import forms
from django.utils import timezone


class PublishOfferForm(forms.Form):
    item = forms.ChoiceField(label='Inventory item')
    quantity = forms.IntegerField(min_value=1, max_value=2147483647)
    notes = forms.CharField(max_length=1000, required=False)

    def __init__(self, *args, items, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].choices = [(item['value'], item['label']) for item in items]


class BorrowRequestForm(forms.Form):
    offer_id = forms.IntegerField(min_value=1, max_value=9223372036854775807)
    quantity = forms.IntegerField(min_value=1, max_value=2147483647)
    due_date = forms.DateField(input_formats=['%Y-%m-%d'])
    purpose = forms.CharField(max_length=1000)

    def clean_due_date(self):
        due_date = self.cleaned_data['due_date']
        if due_date < timezone.localdate():
            raise forms.ValidationError('Choose today or a future return date.')
        return due_date


class LoanActionForm(forms.Form):
    loan_id = forms.IntegerField(min_value=1, max_value=9223372036854775807)
    note = forms.CharField(max_length=1000, required=False)


class WithdrawOfferForm(forms.Form):
    offer_id = forms.IntegerField(min_value=1, max_value=9223372036854775807)
