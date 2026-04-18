from django import forms

from accounts.station_access import visible_stations
from inventory.models import FuelTank

from .models import DeliveryReceipt, FuelPurchaseOrder, Supplier


FORM_INPUT = "w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-[#0f7ea6] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#0f7ea6]/20"
FORM_SELECT = FORM_INPUT
FORM_TEXTAREA = FORM_INPUT + " min-h-[110px]"
FORM_CHECKBOX = "h-4 w-4 rounded border-slate-300 text-[#0f7ea6] focus:ring-[#0f7ea6]"


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": FORM_INPUT, "placeholder": "Supplier name"}),
            "contact_person": forms.TextInput(attrs={"class": FORM_INPUT, "placeholder": "Contact person"}),
            "phone": forms.TextInput(attrs={"class": FORM_INPUT, "placeholder": "+250..." }),
            "email": forms.EmailInput(attrs={"class": FORM_INPUT, "placeholder": "email@example.com"}),
            "address": forms.TextInput(attrs={"class": FORM_INPUT, "placeholder": "Supplier address"}),
        }


class FuelPurchaseOrderForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["station"].queryset = visible_stations(user)

    class Meta:
        model = FuelPurchaseOrder
        fields = [
            "supplier",
            "station",
            "fuel_type",
            "volume_liters",
            "unit_cost",
            "expected_delivery_date",
            "reference",
            "status",
            "notes",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": "form-select"}),
            "station": forms.Select(attrs={"class": "form-select"}),
            "fuel_type": forms.Select(attrs={"class": "form-select"}),
            "volume_liters": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0.01", "placeholder": "Ordered volume"}
            ),
            "unit_cost": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "min": "0", "placeholder": "Optional"}
            ),
            "expected_delivery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "reference": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. PO-2026-0001"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea min-h-[110px]",
                    "placeholder": "Supplier instructions or receiving notes",
                    "rows": 4,
                }
            ),
        }


class DeliveryReceiptForm(forms.ModelForm):
    class Meta:
        model = DeliveryReceipt
        fields = [
            "purchase_order",
            "tank",
            "delivered_volume",
            "unit_cost",
            "delivery_reference",
            "delivery_date",
            "status",
            "document",
            "notes",
        ]
        widgets = {
            "purchase_order": forms.Select(attrs={"class": FORM_SELECT}),
            "tank": forms.Select(attrs={"class": FORM_SELECT}),
            "delivered_volume": forms.NumberInput(attrs={"class": FORM_INPUT, "step": "0.01", "min": "0.01"}),
            "unit_cost": forms.NumberInput(attrs={"class": FORM_INPUT, "step": "0.01", "min": "0"}),
            "delivery_reference": forms.TextInput(attrs={"class": FORM_INPUT, "placeholder": "Delivery note / invoice no."}),
            "delivery_date": forms.DateInput(attrs={"class": FORM_INPUT, "type": "date"}),
            "status": forms.Select(attrs={"class": FORM_SELECT}),
            "document": forms.ClearableFileInput(attrs={"class": FORM_INPUT}),
            "notes": forms.Textarea(attrs={"class": FORM_TEXTAREA, "placeholder": "Receiving remarks"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["purchase_order"].queryset = FuelPurchaseOrder.objects.select_related("supplier", "station").order_by("-created_at")
        self.fields["tank"].queryset = FuelTank.objects.select_related("station").order_by("station__name", "name")
        self.fields["status"].choices = [
            (DeliveryReceipt.Status.DRAFT, "Draft"),
            (DeliveryReceipt.Status.PENDING, "Pending"),
            (DeliveryReceipt.Status.CANCELLED, "Cancelled"),
        ]

        purchase_order_id = (
            self.data.get("purchase_order")
            or self.initial.get("purchase_order")
            or getattr(self.instance, "purchase_order_id", None)
        )
        if purchase_order_id:
            try:
                purchase_order = FuelPurchaseOrder.objects.get(pk=purchase_order_id)
                self.fields["tank"].queryset = FuelTank.objects.filter(
                    station_id=purchase_order.station_id,
                    fuel_type=purchase_order.fuel_type,
                    is_active=True,
                ).order_by("name")
                if not self.initial.get("unit_cost") and purchase_order.unit_cost is not None:
                    self.initial["unit_cost"] = purchase_order.unit_cost
            except FuelPurchaseOrder.DoesNotExist:
                pass

    def clean_status(self):
        status = self.cleaned_data["status"]
        if status == DeliveryReceipt.Status.RECEIVED:
            raise forms.ValidationError("Use the Post Receipt action to mark a delivery as received.")
        return status
