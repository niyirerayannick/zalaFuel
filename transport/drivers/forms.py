from django import forms
from .models import Driver


class DriverForm(forms.ModelForm):
    """Form for creating and updating drivers"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'e.g. driver@example.com'
        }),
        help_text='Contact email only. Drivers do not receive system logins.'
    )
    
    class Meta:
        model = Driver
        fields = [
            'name', 'email', 'phone', 'license_number', 
            'license_category', 'license_expiry', 'license_photo', 'work_status', 'status', 'assigned_vehicle', 'availability_status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter driver full name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g. +250788000000'
            }),
            'license_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter license number'
            }),
            'license_category': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'license_expiry': forms.DateInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'type': 'date'
            }),
            'license_photo': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'work_status': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'assigned_vehicle': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'availability_status': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
        }
        labels = {
            'name': 'Driver Full Name',
            'phone': 'Phone Number',
            'license_number': 'License Number',
            'license_category': 'License Category',
            'license_expiry': 'License Expiry Date',
            'license_photo': 'Driving License Photo',
            'work_status': 'Work Status',
            'status': 'Status',
            'assigned_vehicle': 'Assigned Vehicle',
            'availability_status': 'Availability',
        }

    def clean_license_expiry(self):
        license_expiry = self.cleaned_data.get('license_expiry')
        if license_expiry:
            from django.utils import timezone
            if license_expiry < timezone.now().date():
                raise forms.ValidationError("License expiry date cannot be in the past.")
        return license_expiry

    def clean_license_number(self):
        license_number = self.cleaned_data.get('license_number')
        if license_number:
            existing = Driver.objects.filter(license_number=license_number)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError("A driver with this license number already exists.")
                
        return license_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
        return email


class DriverSearchForm(forms.Form):
    """Form for searching drivers"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Search by name or license number...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Driver.DriverStatus.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
