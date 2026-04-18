from django import forms

from .models import Tank, TankStockEntry


class TankForm(forms.ModelForm):
    class Meta:
        model = Tank
        fields = ["terminal", "product", "name", "code", "capacity_liters", "current_stock_liters", "minimum_threshold", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["product"].queryset = self.fields["product"].queryset.filter(status="active")


class TankStockEntryForm(forms.ModelForm):
    date_input_format = "%Y-%m-%d"

    class Meta:
        model = TankStockEntry
        fields = ["tank", "entry_date", "opening_stock", "stock_in", "stock_out", "closing_stock", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["entry_date"].widget = forms.DateInput(
            format=self.date_input_format,
            attrs={
                "type": "date",
                "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
            },
        )
        self.fields["entry_date"].input_formats = [self.date_input_format]
        self.fields["remarks"].widget.attrs["rows"] = 3
