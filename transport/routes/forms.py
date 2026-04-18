from django import forms
from .models import Route


class RouteForm(forms.ModelForm):
    """Form for creating and updating routes"""
    
    class Meta:
        model = Route
        fields = [
            'origin', 'destination', 'distance_km', 'is_active'
        ]
        widgets = {
            'origin': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter origin location'
            }),
            'destination': forms.TextInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter destination location'
            }),
            'distance_km': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Enter distance in kilometers',
                'step': '0.01',
                'min': '0'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }
        labels = {
            'origin': 'Origin Location',
            'destination': 'Destination Location',
            'distance_km': 'Distance (km)',
            'is_active': 'Active Route',
        }

    def clean(self):
        cleaned_data = super().clean()
        origin = cleaned_data.get('origin')
        destination = cleaned_data.get('destination')
        
        if origin and destination:
            if origin.lower() == destination.lower():
                raise forms.ValidationError("Origin and destination cannot be the same.")
                
            # Check for duplicate routes (excluding current instance on update)
            existing = Route.objects.filter(
                origin__iexact=origin, 
                destination__iexact=destination
            )
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
                
            if existing.exists():
                raise forms.ValidationError("A route from this origin to this destination already exists.")
        
        return cleaned_data

    def clean_distance_km(self):
        distance_km = self.cleaned_data.get('distance_km')
        if distance_km is not None and distance_km <= 0:
            raise forms.ValidationError("Distance must be greater than zero.")
        return distance_km


class RouteSearchForm(forms.Form):
    """Form for searching routes"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Search by origin or destination...'
        })
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All Routes'), ('true', 'Active Routes'), ('false', 'Inactive Routes')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )