from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import MaintenanceRecord, default_service_types
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle


class MaintenanceRecordForm(forms.ModelForm):
    """Form for creating and updating maintenance records"""
    
    class Meta:
        model = MaintenanceRecord
        fields = [
            'vehicle', 'trip', 'service_type', 'service_date', 'service_km',
            'cost', 'workshop', 'downtime_days'
        ]
        widgets = {
            'vehicle': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'required': True
            }),
            'trip': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
            }),
            'service_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'required': True,
            }),
            'service_date': forms.DateInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'type': 'date',
                'required': True
            }),
            'service_km': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'min': '0',
                'required': True,
                'placeholder': 'Current odometer reading'
            }),
            'cost': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'step': '0.01',
                'min': '0',
                'required': True,
                'placeholder': '0.00'
            }),
            'workshop': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'required': True,
                'placeholder': 'Service center or workshop name'
            }),
            'downtime_days': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm',
                'min': '0',
                'value': '0',
                'placeholder': 'Number of days vehicle was out of service'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['trip'].required = False
        self.fields['trip'].queryset = Trip.objects.select_related('vehicle', 'customer').order_by('-created_at')
        existing_service_types = list(
            MaintenanceRecord.objects.order_by().values_list('service_type', flat=True).distinct()
        )
        service_types = []
        seen = set()
        for item in default_service_types() + existing_service_types:
            value = (item or "").strip()
            if value and value not in seen:
                seen.add(value)
                service_types.append((value, value))
        self.fields['service_type'].choices = [("", "Select service type...")] + service_types
        
        # Set help texts
        self.fields['vehicle'].help_text = "Select the vehicle that received maintenance"
        self.fields['trip'].help_text = "Optional. If you select a trip, the vehicle will follow the trip's assigned vehicle automatically."
        self.fields['service_type'].help_text = "Type of maintenance performed"
        self.fields['service_date'].help_text = "Date the service was performed"
        self.fields['service_km'].help_text = "Odometer reading at time of service"
        self.fields['cost'].help_text = "Total cost of the maintenance service"
        self.fields['workshop'].help_text = "Name of the workshop or service center"
        self.fields['downtime_days'].help_text = "Number of days the vehicle was out of service (0 if no downtime)"

    def clean_service_date(self):
        service_date = self.cleaned_data.get('service_date')
        
        if service_date and service_date > timezone.now().date():
            raise ValidationError("Service date cannot be in the future.")
        
        return service_date

    def clean_service_km(self):
        service_km = self.cleaned_data.get('service_km')
        vehicle = self.cleaned_data.get('vehicle')
        
        if service_km and vehicle:
            # Check if the service km is reasonable compared to last service
            if hasattr(vehicle, 'last_service_km') and vehicle.last_service_km:
                if service_km < vehicle.last_service_km:
                    raise ValidationError(
                        f"Service kilometer ({service_km:,}) cannot be less than "
                        f"the last recorded service kilometer ({vehicle.last_service_km:,})."
                    )
        
        return service_km

    def clean_cost(self):
        cost = self.cleaned_data.get('cost')
        
        if cost and cost <= 0:
            raise ValidationError("Maintenance cost must be greater than zero.")
        
        return cost

    def clean_downtime_days(self):
        downtime_days = self.cleaned_data.get('downtime_days')
        
        if downtime_days and downtime_days < 0:
            raise ValidationError("Downtime days cannot be negative.")
        
        return downtime_days

    def clean(self):
        cleaned_data = super().clean()
        trip = cleaned_data.get('trip')
        vehicle = cleaned_data.get('vehicle')
        service_date = cleaned_data.get('service_date')
        downtime_days = cleaned_data.get('downtime_days', 0)

        if trip and trip.vehicle_id:
            if vehicle and trip.vehicle_id != vehicle.id:
                cleaned_data['vehicle'] = trip.vehicle
            elif not vehicle:
                cleaned_data['vehicle'] = trip.vehicle
        
        if service_date and downtime_days and downtime_days > 0:
            # Calculate end date of downtime
            from datetime import timedelta
            end_date = service_date + timedelta(days=downtime_days)
            
            if end_date > timezone.now().date():
                # This is fine, just noting that the vehicle is still in maintenance
                pass
        
        return cleaned_data
