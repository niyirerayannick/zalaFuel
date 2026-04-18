from django import forms

from .models import Nozzle, Pump
from inventory.models import FuelTank


class NozzleForm(forms.ModelForm):
    class Meta:
        model = Nozzle
        fields = ["pump", "fuel_type", "tank", "meter_start", "meter_end", "is_active"]
        widgets = {
            "pump": forms.Select(attrs={"class": "form-select"}),
            "fuel_type": forms.Select(attrs={"class": "form-select"}),
            "tank": forms.Select(attrs={"class": "form-select"}),
            "meter_start": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "meter_end": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        pump_id = kwargs.pop("pump_id", None)
        super().__init__(*args, **kwargs)
        if pump_id:
            try:
                pump = Pump.objects.select_related("station").get(pk=pump_id)
                self.fields["pump"].initial = pump
                self.fields["tank"].queryset = FuelTank.objects.filter(station=pump.station)
            except Pump.DoesNotExist:
                pass
        else:
            self.fields["tank"].queryset = FuelTank.objects.all()

