from django import forms

from .models import ProductReceipt


class ProductReceiptForm(forms.ModelForm):
    class Meta:
        model = ProductReceipt
        fields = ["supplier", "product", "quantity_received", "terminal", "tank", "reference_number", "receipt_date", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["remarks"].widget.attrs["rows"] = 3

