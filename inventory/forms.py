from django import forms

from accounts.station_access import visible_stations

from .models import FuelTank


class TankForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["station"].queryset = visible_stations(user)

    class Meta:
        model = FuelTank
        fields = ["station", "name", "fuel_type", "capacity_liters", "low_level_threshold", "is_active"]
        widgets = {
            "station": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Tank name"}),
            "fuel_type": forms.Select(attrs={"class": "form-select"}),
            "capacity_liters": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "low_level_threshold": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }
