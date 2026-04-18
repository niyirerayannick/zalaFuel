from django import forms

from .models import Product, Supplier


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["name", "code", "category", "unit", "default_price", "is_active"]


class SupplierForm(StyledModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "source_location"]

