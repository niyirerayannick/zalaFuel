from django import forms
from .models import Vehicle, VehicleOwner


class VehicleOwnerForm(forms.ModelForm):
    class Meta:
        model = VehicleOwner
        fields = ["name", "phone", "bank_name", "bank_account"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-lg border-slate-300 text-sm focus:border-green-700 focus:ring-green-700",
                    "placeholder": "Owner full name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-lg border-slate-300 text-sm focus:border-green-700 focus:ring-green-700",
                    "placeholder": "Phone number",
                }
            ),
            "bank_name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-lg border-slate-300 text-sm focus:border-green-700 focus:ring-green-700",
                    "placeholder": "Bank name",
                }
            ),
            "bank_account": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-lg border-slate-300 text-sm focus:border-green-700 focus:ring-green-700",
                    "placeholder": "Bank account number",
                }
            ),
        }

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

class VehicleForm(forms.ModelForm):
    """Form for creating and updating vehicles"""
    new_owner_name = forms.CharField(required=False)
    new_owner_phone = forms.CharField(required=False)
    new_owner_bank_name = forms.CharField(required=False)
    new_owner_bank_account = forms.CharField(required=False)
    
    class Meta:
        model = Vehicle
        fields = [
            'plate_number', 'vehicle_model', 'vehicle_type', 'year', 'fuel_type',
            'engine_capacity', 'color', 'capacity', 'ownership_type', 'owner', 'current_odometer',
            'status', 'insurance_expiry', 'inspection_expiry', 
            'service_interval_km', 'last_service_km'
        ]
        widgets = {
            'plate_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'Enter plate number'
            }),
            'vehicle_model': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. Toyota Hilux'
            }),
            'vehicle_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'year': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '1950',
                'placeholder': 'e.g. 2023'
            }),
            'fuel_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'engine_capacity': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. 2.8L'
            }),
            'color': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'placeholder': 'e.g. White'
            }),
            'capacity': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'step': '0.5',
                'min': '0.5',
                'placeholder': 'Capacity in tons'
            }),
            'ownership_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'owner': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
            }),
            'current_odometer': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'step': '1',
                'min': '0',
                'placeholder': 'Current odometer reading'
            }),
            'status': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
            }),
            'insurance_expiry': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'type': 'date',
            }),
            'inspection_expiry': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'type': 'date',
            }),
            'service_interval_km': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'min': '1000',
                'step': '1000',
                'placeholder': 'Service interval in kilometers'
            }),
            'last_service_km': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',  
                'min': '0',
                'placeholder': 'Last service odometer reading'
            })
        }

    def clean_plate_number(self):
        plate_number = self.cleaned_data.get("plate_number", "")
        return plate_number.upper().strip()

    def clean(self):
        cleaned_data = super().clean()
        ownership_type = cleaned_data.get("ownership_type")
        owner = cleaned_data.get("owner")
        new_owner_name = (cleaned_data.get("new_owner_name") or "").strip()
        self.instance._pending_new_owner = False

        if ownership_type == Vehicle.OwnershipType.EXTERNAL:
            if not owner and not new_owner_name:
                self.add_error("owner", "Select an owner or add a new one for external vehicles.")
                self.add_error("new_owner_name", "New owner name is required when no owner is selected.")
            elif not owner and new_owner_name:
                self.instance._pending_new_owner = True
        elif ownership_type == Vehicle.OwnershipType.COMPANY:
            cleaned_data["owner"] = None

        return cleaned_data

    def save(self, commit=True):
        vehicle = super().save(commit=False)
        ownership_type = self.cleaned_data.get("ownership_type")
        owner = self.cleaned_data.get("owner")

        if ownership_type == Vehicle.OwnershipType.EXTERNAL and not owner:
            owner = VehicleOwner.objects.create(
                name=(self.cleaned_data.get("new_owner_name") or "").strip(),
                phone=(self.cleaned_data.get("new_owner_phone") or "").strip(),
                bank_name=(self.cleaned_data.get("new_owner_bank_name") or "").strip(),
                bank_account=(self.cleaned_data.get("new_owner_bank_account") or "").strip(),
            )

        vehicle.owner = owner if ownership_type == Vehicle.OwnershipType.EXTERNAL else None
        vehicle._pending_new_owner = False
        if commit:
            vehicle.save()
        return vehicle

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["capacity"].label = "Load Capacity"
        self.fields["capacity"].help_text = "Vehicle load capacity in tons"
        self.fields["owner"].queryset = VehicleOwner.objects.order_by("name")
        self.fields["owner"].required = False
        self.fields["ownership_type"].label = "Ownership Type"
        self.fields["owner"].label = "Vehicle Owner"
        self.fields["owner"].empty_label = "Select existing owner"
        self.fields["owner"].help_text = "Choose the external owner when this vehicle is rented."
        self.fields["new_owner_name"].label = "New Owner Name"
        self.fields["new_owner_phone"].label = "New Owner Phone"
        self.fields["new_owner_bank_name"].label = "Bank Name"
        self.fields["new_owner_bank_account"].label = "Bank Account"
        for field_name, placeholder in {
            "new_owner_name": "Enter owner name",
            "new_owner_phone": "Enter owner phone",
            "new_owner_bank_name": "Enter bank name",
            "new_owner_bank_account": "Enter bank account",
        }.items():
            self.fields[field_name].widget.attrs.update(
                {
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500",
                    "placeholder": placeholder,
                }
            )
