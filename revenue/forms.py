from django import forms

from .models import RevenueEntry


class RevenueEntryForm(forms.ModelForm):
    class Meta:
        model = RevenueEntry
        fields = ["terminal", "product", "omc", "volume_liters", "amount", "revenue_date", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["notes"].widget.attrs["rows"] = 3

