from django import forms

from .models import OMC


class OMCForm(forms.ModelForm):
    class Meta:
        model = OMC
        fields = ["name", "code", "contact_person", "phone", "email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )

