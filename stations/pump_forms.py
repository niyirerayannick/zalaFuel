from django import forms

from .models import Pump


class PumpForm(forms.ModelForm):
    class Meta:
        model = Pump
        fields = ["station", "label", "tank", "is_active"]
        widgets = {
            "station": forms.Select(attrs={"class": "form-select"}),
            "label": forms.TextInput(attrs={"class": "form-input", "placeholder": "Pump label"}),
            "tank": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        station_id = None
        # Use station_id only — accessing .station on an unsaved Pump without FK raises RelatedObjectDoesNotExist.
        if getattr(self.instance, "station_id", None):
            station_id = self.instance.station_id
        elif self.data and self.data.get('station'):
            station_id = self.data.get('station')
        elif self.initial.get('station'):
            station_id = self.initial.get('station')
        if station_id:
            try:
                from stations.models import Station
                station = Station.objects.get(pk=station_id)
                self.fields['tank'].queryset = station.tanks.filter(is_active=True)
            except Station.DoesNotExist:
                self.fields['tank'].queryset = self.fields['tank'].queryset.none()
        else:
            self.fields['tank'].queryset = self.fields['tank'].queryset.none()
