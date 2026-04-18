from django import forms

from .models import Dispatch


class DispatchForm(forms.ModelForm):
    class Meta:
        model = Dispatch
        fields = ["product", "quantity_dispatched", "terminal", "tank", "omc", "destination", "reference_number", "dispatch_date", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["remarks"].widget.attrs["rows"] = 3

