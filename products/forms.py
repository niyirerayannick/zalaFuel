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
        fields = ["product_name", "product_code", "product_type", "unit_of_measure", "description", "status", "density", "temperature_factor", "color_marker", "display_order"]


class SupplierForm(StyledModelForm):
    class Meta:
        model = Supplier
        fields = ["supplier_name", "supplier_code", "contact_person", "phone", "email", "address", "country", "status"]

