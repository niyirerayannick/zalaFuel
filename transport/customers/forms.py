from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    """Form for creating and updating customers"""
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'e.g. client@example.com'
        }),
        help_text='An account will be created and credentials sent to this email'
    )
    
    create_account = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-green-600 focus:ring-green-500 border-gray-300 rounded'
        }),
        label='Create client account',
        help_text='Automatically create a login account and send credentials via email'
    )
    
    class Meta:
        model = Customer
        fields = [
            'company_name', 'contact_person', 'phone', 'email', 
            'address', 'status'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter customer name'
            }),
            'contact_person': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter contact person name'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter phone number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter email address'
            }),
            'address': forms.Textarea(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter full address',
                'rows': 3
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
        }
        labels = {
            'company_name': 'Customer Name',
            'contact_person': 'Contact Person', 
            'phone': 'Phone Number',
            'email': 'Email Address',
            'address': 'Address',
            'status': 'Status',
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            # Check for duplicate emails (excluding current instance on update)
            existing = Customer.objects.filter(email=email)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
                
            if existing.exists():
                raise forms.ValidationError("A customer with this email already exists.")
                
        return email


class CustomerSearchForm(forms.Form):
    """Form for searching customers"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Search by name, contact person, or email...'
        })
    )
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Customer.CustomerStatus.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )