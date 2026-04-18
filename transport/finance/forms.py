from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone

from accounts.currency import CURRENCY_SYMBOLS
from accounts.models import SystemSettings
from transport.customers.models import Customer
from transport.drivers.models import Driver
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle

from .models import DriverAllowance, DriverFee, Expense, ExpenseType, Payment, ensure_default_expense_types


FORM_CONTROL = (
    "mt-2 block w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 "
    "shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition duration-200 placeholder:text-slate-400 "
    "focus:border-green-600 focus:ring-4 focus:ring-green-100 focus:outline-none"
)
ICON_CONTROL = FORM_CONTROL + " pl-11"
AMOUNT_CONTROL = FORM_CONTROL + " pl-16"
TEXTAREA_CONTROL = FORM_CONTROL + " min-h-[120px] resize-y pl-11"


def _system_currency_context():
    currency_code = getattr(settings, "DEFAULT_CURRENCY", "USD")
    currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    try:
        system_settings = SystemSettings.get_settings()
    except Exception:
        system_settings = None
    if system_settings:
        currency_code = system_settings.currency or currency_code
        currency_symbol = system_settings.currency_symbol or CURRENCY_SYMBOLS.get(currency_code, currency_code)
    return currency_code, currency_symbol


def _apply_currency_field_context(field, label):
    currency_code, currency_symbol = _system_currency_context()
    field.label = f"{label} ({currency_code})"
    field.widget.attrs["placeholder"] = f"{currency_symbol} 0.00"
    field.widget.attrs["data-currency-code"] = currency_code
    field.widget.attrs["data-currency-symbol"] = currency_symbol
    field.help_text = f"Enter the amount in the system currency ({currency_code})."


class PaymentForm(forms.ModelForm):
    """Form for creating and updating payments."""

    class Meta:
        model = Payment
        fields = [
            "order",
            "trip",
            "customer",
            "amount",
            "amount_paid",
            "payment_date",
            "status",
            "payment_method",
            "reference",
            "proof_document",
            "failure_reason",
            "notes",
        ]
        widgets = {
            "order": forms.Select(attrs={"class": ICON_CONTROL}),
            "trip": forms.Select(attrs={"class": ICON_CONTROL}),
            "customer": forms.Select(attrs={"class": ICON_CONTROL}),
            "amount": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "required": True, "placeholder": "0.00"}),
            "amount_paid": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "placeholder": "0.00"}),
            "payment_date": forms.DateInput(attrs={"class": ICON_CONTROL, "type": "date", "required": True}),
            "status": forms.Select(attrs={"class": ICON_CONTROL}),
            "payment_method": forms.Select(attrs={"class": ICON_CONTROL}),
            "reference": forms.TextInput(attrs={"class": ICON_CONTROL, "placeholder": "Receipt, bank reference, or invoice code"}),
            "proof_document": forms.ClearableFileInput(attrs={"class": FORM_CONTROL, "accept": ".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx"}),
            "failure_reason": forms.Textarea(attrs={"class": TEXTAREA_CONTROL, "rows": 3, "placeholder": "Explain why the payment failed"}),
            "notes": forms.Textarea(attrs={"class": TEXTAREA_CONTROL, "rows": 4, "placeholder": "Add context for finance reporting, reconciliation, or approvals"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from transport.orders.models import Order

        self.fields["order"].required = False
        self.fields["trip"].required = False
        self.fields["customer"].required = False
        self.fields["amount_paid"].required = False
        self.fields["failure_reason"].required = False
        order_queryset = Order.objects.select_related("customer").order_by("-created_at")
        trip_queryset = Trip.objects.filter(
            status__in=[Trip.TripStatus.DELIVERED, Trip.TripStatus.CLOSED]
        ).select_related("customer", "route")

        if self.instance.pk:
            if self.instance.order_id:
                order_queryset = Order.objects.filter(Q(pk=self.instance.order_id) | Q(pk__in=order_queryset.values("pk"))).select_related("customer").order_by("-created_at")
            if self.instance.trip_id:
                trip_queryset = Trip.objects.filter(Q(pk=self.instance.trip_id) | Q(pk__in=trip_queryset.values("pk"))).select_related("customer", "route")

        self.fields["order"].queryset = order_queryset
        self.fields["trip"].queryset = trip_queryset
        self.fields["customer"].queryset = Customer.objects.all().order_by("company_name")
        self.fields["trip"].help_text = "Optional for manual revenue. Select a completed trip to use trip-linked revenue."
        self.fields["customer"].help_text = "Optional for trip-linked revenue. Required only when recording manual revenue without an order."
        self.fields["payment_method"].empty_label = None
        _apply_currency_field_context(self.fields["amount"], "Amount")
        _apply_currency_field_context(self.fields["amount_paid"], "Amount Paid")
        self.fields["amount_paid"].help_text = "Used when the payment status is partial."

    def clean_payment_date(self):
        payment_date = self.cleaned_data.get("payment_date")
        if payment_date and payment_date > timezone.now().date():
            raise ValidationError("Payment date cannot be in the future.")
        return payment_date

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount and amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        return amount

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get("amount_paid")
        if amount_paid is not None and amount_paid < 0:
            raise ValidationError("Amount paid cannot be negative.")
        return amount_paid

    def clean(self):
        cleaned_data = super().clean()
        order = cleaned_data.get("order")
        trip = cleaned_data.get("trip")
        customer = cleaned_data.get("customer")
        amount = cleaned_data.get("amount")
        amount_paid = cleaned_data.get("amount_paid") or Decimal("0")
        status = cleaned_data.get("status")
        failure_reason = (cleaned_data.get("failure_reason") or "").strip()

        # Preserve existing finance linkage when editing auto-generated invoices.
        if self.instance.pk:
            if not trip and self.instance.trip_id:
                trip = self.instance.trip
                cleaned_data["trip"] = trip
            if not order and self.instance.order_id:
                order = self.instance.order
                cleaned_data["order"] = order

        if not order and not trip and not customer:
            raise ValidationError("Select an order, trip, or customer so this revenue entry has financial context.")

        if trip and not customer:
            cleaned_data["customer"] = trip.customer
        if order and not customer:
            cleaned_data["customer"] = order.customer
        if trip and not order and trip.job_id:
            cleaned_data["order"] = trip.job

        if trip and amount and trip.revenue and amount > trip.revenue * Decimal("1.2"):
            raise ValidationError(
                f"Payment amount ({amount}) seems high compared to trip revenue ({trip.revenue}). Please verify the amount."
            )

        if status == Payment.Status.PARTIAL:
            if amount_paid <= 0:
                self.add_error("amount_paid", "Enter the amount paid for a partial payment.")
            elif amount and amount_paid >= amount:
                self.add_error("amount_paid", "Amount paid must be less than the invoice amount for a partial payment.")
        elif status == Payment.Status.PAID:
            cleaned_data["amount_paid"] = amount or Decimal("0")
            cleaned_data["failure_reason"] = ""
        elif status == Payment.Status.FAILED:
            cleaned_data["amount_paid"] = Decimal("0")
            if not failure_reason:
                self.add_error("failure_reason", "Explain why the payment failed.")
        else:
            cleaned_data["amount_paid"] = Decimal("0")
            cleaned_data["failure_reason"] = ""

        return cleaned_data


class ExpenseForm(forms.ModelForm):
    custom_type_name = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(
            attrs={
                "class": ICON_CONTROL,
                "placeholder": "Enter a new expense name",
            }
        ),
        label="Other Expense Name",
    )

    """Form for creating and updating expenses."""

    class Meta:
        model = Expense
        fields = ["trip", "vehicle", "type", "status", "amount", "liters", "fuel_unit_price", "expense_date", "proof_document", "description"]
        widgets = {
            "trip": forms.Select(attrs={"class": ICON_CONTROL}),
            "vehicle": forms.Select(attrs={"class": ICON_CONTROL}),
            "type": forms.Select(attrs={"class": ICON_CONTROL, "required": True}),
            "status": forms.Select(attrs={"class": ICON_CONTROL}),
            "amount": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "placeholder": "Total amount"}),
            "liters": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "placeholder": "Fuel quantity in liters"}),
            "fuel_unit_price": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "placeholder": "Unit price per liter"}),
            "expense_date": forms.DateInput(attrs={"class": ICON_CONTROL, "type": "date", "required": True}),
            "proof_document": forms.ClearableFileInput(attrs={"class": FORM_CONTROL, "accept": ".pdf,.png,.jpg,.jpeg,.webp,.doc,.docx"}),
            "description": forms.Textarea(attrs={"class": TEXTAREA_CONTROL, "rows": 4, "placeholder": "Describe what this expense covered and why it was incurred"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_default_expense_types()
        self.fields["trip"].queryset = Trip.objects.all().select_related("customer", "route", "vehicle")
        self.fields["trip"].required = False
        self.fields["vehicle"].queryset = Vehicle.objects.all().order_by("plate_number")
        self.fields["vehicle"].required = False
        self.fields["type"].queryset = ExpenseType.objects.filter(is_active=True).order_by("name")
        self.fields["type"].label = "Expense Category"
        self.fields["status"].required = False
        self.fields["amount"].required = False
        _apply_currency_field_context(self.fields["amount"], "Total Amount")
        self.fields["liters"].label = "Fuel Quantity (Liters)"
        _apply_currency_field_context(self.fields["fuel_unit_price"], "Unit Price / Liter")
        self.fields["liters"].required = False
        self.fields["fuel_unit_price"].required = False
        self.fields["fuel_unit_price"].help_text = "Enter the fuel unit price in the system currency."
        self.fields["expense_date"].required = False
        self.fields["expense_date"].initial = timezone.now().date()
        self.fields["proof_document"].required = False
        self.fields["status"].help_text = "Use Pending until the expense is approved or fully paid."
        other_expense = ExpenseType.objects.filter(name__iexact="Other Expense").first()
        if other_expense:
            current_choices = list(self.fields["type"].choices)
            relabeled_choices = []
            for value, label in current_choices:
                if str(value) == str(other_expense.pk):
                    relabeled_choices.append((value, "Other Expense"))
                else:
                    relabeled_choices.append((value, label))
            self.fields["type"].choices = relabeled_choices
        self.fields["custom_type_name"].help_text = "If you choose Other Expense, enter the expense name to save it for future use."

    def clean_liters(self):
        liters = self.cleaned_data.get("liters")
        if liters is not None and liters <= 0:
            raise ValidationError("Fuel liters must be greater than zero.")
        return liters

    def clean_fuel_unit_price(self):
        fuel_unit_price = self.cleaned_data.get("fuel_unit_price")
        if fuel_unit_price is not None and fuel_unit_price <= 0:
            raise ValidationError("Fuel unit price must be greater than zero.")
        return fuel_unit_price

    def clean_expense_date(self):
        expense_date = self.cleaned_data.get("expense_date")
        if expense_date and expense_date > timezone.now().date():
            raise ValidationError("Expense date cannot be in the future.")
        return expense_date

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise ValidationError("Expense amount must be greater than zero.")
        return amount

    def clean_description(self):
        description = self.cleaned_data.get("description")
        if description and len(description.strip()) < 10:
            raise ValidationError("Please provide a more detailed description (at least 10 characters).")
        return description

    def clean(self):
        cleaned_data = super().clean()
        trip = cleaned_data.get("trip")
        vehicle = cleaned_data.get("vehicle")
        expense_type = cleaned_data.get("type")
        status = cleaned_data.get("status")
        description = (cleaned_data.get("description") or "").strip()
        custom_type_name = (cleaned_data.get("custom_type_name") or "").strip()
        liters = cleaned_data.get("liters")
        amount = cleaned_data.get("amount")
        fuel_unit_price = cleaned_data.get("fuel_unit_price")
        if trip and not vehicle:
            cleaned_data["vehicle"] = trip.vehicle
        if expense_type and expense_type.name.strip().lower() == "other expense":
            if not custom_type_name:
                self.add_error("custom_type_name", "Enter the other expense name.")
            else:
                custom_expense_type, _created = ExpenseType.objects.get_or_create(
                    name=custom_type_name,
                    defaults={"is_active": True},
                )
                if not custom_expense_type.is_active:
                    custom_expense_type.is_active = True
                    custom_expense_type.save(update_fields=["is_active", "updated_at"])
                cleaned_data["type"] = custom_expense_type
                expense_type = custom_expense_type
        if expense_type:
            cleaned_data["category"] = expense_type.name
            if expense_type.name.strip().lower() != "fuel":
                cleaned_data["liters"] = None
                cleaned_data["fuel_unit_price"] = None
                if amount is None or amount <= 0:
                    self.add_error("amount", "Expense amount must be greater than zero.")
            else:
                if liters is None:
                    self.add_error("liters", "Enter fuel liters.")
                if fuel_unit_price is None:
                    self.add_error("fuel_unit_price", "Enter the fuel unit price.")
                if liters is not None and fuel_unit_price is not None:
                    cleaned_data["amount"] = (liters * fuel_unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if status == Expense.Status.REJECTED and not description:
            self.add_error("description", "Add a reason when rejecting an expense record.")
        return cleaned_data


class DriverAllowanceForm(forms.ModelForm):
    class Meta:
        model = DriverAllowance
        fields = ["trip", "driver", "amount"]
        widgets = {
            "trip": forms.Select(attrs={"class": ICON_CONTROL}),
            "driver": forms.Select(attrs={"class": ICON_CONTROL}),
            "amount": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "required": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["trip"].queryset = Trip.objects.select_related("driver").order_by("-created_at")
        self.fields["driver"].queryset = Driver.objects.order_by("name")
        _apply_currency_field_context(self.fields["amount"], "Allowance Amount")


class DriverFeeForm(forms.ModelForm):
    """Form for capturing driver fees per trip."""

    class Meta:
        model = DriverFee
        fields = ["trip", "driver", "amount", "fee_date", "payment_status", "notes"]
        widgets = {
            "trip": forms.Select(attrs={"class": ICON_CONTROL}),
            "driver": forms.Select(attrs={"class": ICON_CONTROL}),
            "amount": forms.NumberInput(attrs={"class": AMOUNT_CONTROL, "step": "0.01", "min": "0", "required": True, "placeholder": "0.00"}),
            "fee_date": forms.DateInput(attrs={"class": ICON_CONTROL, "type": "date", "required": True}),
            "payment_status": forms.Select(attrs={"class": ICON_CONTROL}),
            "notes": forms.Textarea(attrs={"class": TEXTAREA_CONTROL, "rows": 4, "placeholder": "Capture payout notes, approvals, or exceptions"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["trip"].queryset = Trip.objects.filter(status__in=[Trip.TripStatus.DELIVERED, Trip.TripStatus.CLOSED]).select_related("driver", "customer")
        self.fields["driver"].queryset = Driver.objects.all().order_by("name")
        _apply_currency_field_context(self.fields["amount"], "Driver Fee")

    def clean_fee_date(self):
        fee_date = self.cleaned_data.get("fee_date")
        if fee_date and fee_date > timezone.now().date():
            raise ValidationError("Driver fee date cannot be in the future.")
        return fee_date

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount and amount <= 0:
            raise ValidationError("Driver fee must be greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        trip = cleaned_data.get("trip")
        driver = cleaned_data.get("driver")
        if trip and driver and trip.driver_id != driver.id:
            raise ValidationError("The selected driver must match the driver assigned to the trip.")
        return cleaned_data
