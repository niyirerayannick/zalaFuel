from django import forms

from .models import ProductReceipt
from products.models import Supplier as ProductSupplier
from suppliers.models import Supplier as OperationsSupplier


def _build_supplier_code(source_supplier):
    base_code = f"OPS-{source_supplier.pk:04d}"
    candidate = base_code
    suffix = 1
    while ProductSupplier.objects.filter(supplier_code=candidate).exists():
        suffix += 1
        candidate = f"{base_code}-{suffix}"
    return candidate


def ensure_receipt_suppliers():
    existing_names = {
        (name or "").strip().lower()
        for name in ProductSupplier.objects.values_list("supplier_name", flat=True)
    }
    new_suppliers = []
    for source_supplier in OperationsSupplier.objects.all().order_by("name"):
        normalized_name = (source_supplier.name or "").strip().lower()
        if not normalized_name or normalized_name in existing_names:
            continue
        new_suppliers.append(
            ProductSupplier(
                supplier_name=source_supplier.name,
                supplier_code=_build_supplier_code(source_supplier),
                contact_person=source_supplier.contact_person or "",
                phone=source_supplier.phone or "",
                email=source_supplier.email or "",
                address=source_supplier.address or "",
                status=ProductSupplier.Status.ACTIVE,
            )
        )
        existing_names.add(normalized_name)

    if new_suppliers:
        ProductSupplier.objects.bulk_create(new_suppliers)


class ProductReceiptForm(forms.ModelForm):
    date_input_format = "%Y-%m-%d"

    class Meta:
        model = ProductReceipt
        fields = ["supplier", "product", "quantity_received", "terminal", "tank", "reference_number", "receipt_date", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_receipt_suppliers()
        self.fields["supplier"].queryset = ProductSupplier.objects.order_by("supplier_name")
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["receipt_date"].widget = forms.DateInput(
            format=self.date_input_format,
            attrs={
                "type": "date",
                "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
            },
        )
        self.fields["receipt_date"].input_formats = [self.date_input_format]
        self.fields["remarks"].widget.attrs["rows"] = 3
