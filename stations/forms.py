from django import forms

from .models import Station


class StationForm(forms.ModelForm):
    class Meta:
        model = Station
        fields = ["name", "code", "location", "manager", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Station name"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "Auto-generated", "readonly": "readonly"}),
            "location": forms.TextInput(attrs={"class": "form-input", "placeholder": "City / Address"}),
            "manager": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].required = False
