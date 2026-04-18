from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from accounts.station_access import require_station_access, visible_stations

from .models import ShiftSession, PumpReading, FuelSale, Customer, OMCSalesEntry
from .selectors import station_attendants
from .services import open_shift_conflicts, shift_sales_summary
from stations.models import Station, Pump, Nozzle

User = get_user_model()
DECIMAL_2 = Decimal("0.01")


def quantize_2(value):
    return Decimal(value or 0).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)


# Shared widget helpers
def field_classes(extra=None, readonly=False, placeholder=None, input_type=None):
    attrs = {"class": "driver-modal-field"}
    if readonly:
        attrs["readonly"] = "readonly"
    if placeholder:
        attrs["placeholder"] = placeholder
    if input_type:
        attrs["type"] = input_type
    return attrs if not extra else {**attrs, **extra}


class ShiftOpenForm(forms.ModelForm):
    status = forms.CharField(widget=forms.HiddenInput(), required=False, initial=ShiftSession.Status.OPEN)

    def __init__(self, *args, user=None, **kwargs):
        self._request_user = user
        super().__init__(*args, **kwargs)
        station_id = self.data.get("station") or self.initial.get("station") or getattr(self.instance, "station_id", None)
        if user is not None:
            self.fields["station"].queryset = visible_stations(user)
        else:
            self.fields["station"].queryset = Station.objects.filter(is_active=True).order_by("name")
        self.fields["station"].required = True
        self.fields["attendant"].required = True
        self.fields["shift_type"].required = True
        self.fields["attendant"].queryset = station_attendants(station_id)
        self.fields["attendant"].empty_label = "Select station first" if not station_id else "Select attendant"
        # UI classes
        self.fields["station"].widget.attrs.update(field_classes())
        self.fields["attendant"].widget.attrs.update(field_classes())
        self.fields["shift_type"].widget.attrs.update(field_classes())
        self.fields["opening_cash"].widget.attrs.update(field_classes({"step": "0.01"}))
        self.fields["note"].widget.attrs.update(field_classes({"rows": 2}))
        if self.instance and self.instance.pk:
            self.fields["opened_at_display"] = forms.CharField(
                required=False,
                initial=self.instance.opened_at,
                widget=forms.TextInput(attrs=field_classes(readonly=True)),
                label="Opened At",
            )

    class Meta:
        model = ShiftSession
        fields = ["station", "attendant", "shift_type", "opening_cash", "note", "status"]
        widgets = {
            "note": forms.Textarea(),
        }

    def clean_opening_cash(self):
        cash = self.cleaned_data.get("opening_cash") or Decimal("0")
        if cash < 0:
            raise forms.ValidationError("Opening cash cannot be negative.")
        return cash

    def clean(self):
        cleaned = super().clean()
        station = cleaned.get("station")
        attendant = cleaned.get("attendant")

        if not station:
            self.add_error("station", "Station is required.")
        if not attendant:
            self.add_error("attendant", "Attendant is required.")
        if not cleaned.get("shift_type"):
            self.add_error("shift_type", "Shift type is required.")
        if station and attendant:
            if self._request_user is not None:
                try:
                    require_station_access(self._request_user, station)
                except PermissionDenied:
                    self.add_error("station", "You cannot open a shift for this station.")
            if not attendant.is_active:
                self.add_error("attendant", "Selected attendant is inactive.")
            elif attendant.assigned_station_id != station.id:
                self.add_error("attendant", "Selected attendant is not assigned to this station.")

            conflicts = open_shift_conflicts(station=station, attendant=attendant, exclude_shift=self.instance)
            for field, message in conflicts.items():
                self.add_error(field, message)

        return cleaned


class LegacyShiftCloseForm(forms.ModelForm):
    cash_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    momo_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    pos_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    credit_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["closing_cash"].widget.attrs.update(field_classes({"step": "0.01"}))
        self.fields["note"].widget.attrs.update(field_classes({"rows": 2}))
        for name in ["cash_amount", "momo_amount", "pos_amount", "credit_amount"]:
            self.fields[name].widget.attrs.update(field_classes({"step": "0.01"}))
        if self.instance and self.instance.pk:
            summary = f"Shift #{self.instance.pk} · {self.instance.station} · Sales {self.instance.total_sales}"
            self.fields["closing_summary"] = forms.CharField(
                required=False,
                initial=summary,
                widget=forms.TextInput(attrs=field_classes(readonly=True)),
                label="Shift Summary",
            )

    class Meta:
        model = ShiftSession
        fields = ["closing_cash", "note", "cash_amount", "momo_amount", "pos_amount", "credit_amount"]
        widgets = {"note": forms.Textarea()}

    def clean_closing_cash(self):
        cash = self.cleaned_data.get("closing_cash") or Decimal("0")
        if cash < 0:
            raise forms.ValidationError("Closing cash cannot be negative.")
        return cash


class ShiftCloseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        summary = shift_sales_summary(self.instance) if self.instance and self.instance.pk else None
        self.fields["closing_cash"].required = True
        self.fields["closing_cash"].label = "Closing Amount"
        self.fields["closing_cash"].widget.attrs.update(field_classes({"step": "0.01", "min": "0"}))
        self.fields["closing_note"].required = False
        self.fields["closing_note"].label = "Closing Notes / Remarks"
        self.fields["closing_note"].widget.attrs.update(field_classes({"rows": 3}))
        if self.instance and self.instance.pk:
            self.fields["closing_summary"] = forms.CharField(
                required=False,
                initial=(
                    f"Shift #{self.instance.pk} - {self.instance.station} - "
                    f"Sales {summary['sales_count']} - Gross {summary['total_sales']:.2f}"
                ),
                widget=forms.TextInput(attrs=field_classes(readonly=True)),
                label="Shift Summary",
            )
            self.fields["expected_amount"] = forms.DecimalField(
                required=False,
                initial=summary["expected_cash"],
                widget=forms.NumberInput(attrs=field_classes({"step": "0.01"}, readonly=True)),
                label="Expected cash (cash sales only)",
            )

    class Meta:
        model = ShiftSession
        fields = ["closing_cash", "closing_note"]
        widgets = {"closing_note": forms.Textarea()}

    def _post_clean(self):
        original_status = self.instance.status
        self.instance.status = ShiftSession.Status.CLOSED
        try:
            super()._post_clean()
        finally:
            self.instance.status = original_status

    def clean_closing_cash(self):
        cash = self.cleaned_data.get("closing_cash")
        if cash is None:
            raise forms.ValidationError("Closing amount is required.")
        if cash < 0:
            raise forms.ValidationError("Closing amount cannot be negative.")
        return cash


class FuelSaleForm(forms.ModelForm):
    # UI / helper fields not persisted
    tank_display = forms.CharField(required=False, widget=forms.TextInput(attrs=field_classes(readonly=True)))
    fuel_type_display = forms.CharField(required=False, widget=forms.TextInput(attrs=field_classes(readonly=True)))
    current_stock_display = forms.CharField(required=False, widget=forms.TextInput(attrs=field_classes(readonly=True)))
    active_shift_info = forms.CharField(required=False, widget=forms.TextInput(attrs=field_classes(readonly=True)))
    attendant_info = forms.CharField(required=False, widget=forms.TextInput(attrs=field_classes(readonly=True)))

    # Payment breakdown (not on model but needed for workflow)
    cash_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    momo_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    pos_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    credit_amount = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs=field_classes({"rows": 2})))

    customer = forms.ModelChoiceField(
        queryset=Customer.objects.filter(is_credit_allowed=True).order_by("name"),
        required=False,
        widget=forms.Select(attrs=field_classes({"id": "pos-credit-customer"})),
    )

    pump = forms.ModelChoiceField(
        queryset=Pump.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs=field_classes({"id": "pos-pump"})),
    )

    nozzle = forms.ModelChoiceField(
        queryset=Nozzle.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs=field_classes({"id": "pos-nozzle"})),
    )

    payment_method = forms.ChoiceField(
        choices=FuelSale.PaymentMethod.choices,
        initial=FuelSale.PaymentMethod.CASH,
        widget=forms.Select(attrs=field_classes({"id": "pos-method"})),
    )

    opening_meter = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs=field_classes({"id": "pos-opening", "step": "0.01"})),
    )
    closing_meter = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs=field_classes({"id": "pos-closing", "step": "0.01"})),
    )
    volume_liters = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs=field_classes({"id": "pos-quantity", "step": "0.01", "readonly": "readonly"})),
    )
    unit_price = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs=field_classes({"id": "pos-price", "step": "0.01"})),
    )
    total_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs=field_classes({"id": "pos-total", "step": "0.01", "readonly": "readonly"})),
    )
    customer_name = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs=field_classes({"id": "pos-customer", "placeholder": "Walk-in"})),
    )
    receipt_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs=field_classes({"id": "pos-receipt", "placeholder": "Auto/Manual"})),
    )

    class Meta:
        model = FuelSale
        fields = [
            "pump",
            "nozzle",
            "opening_meter",
            "closing_meter",
            "volume_liters",
            "unit_price",
            "total_amount",
            "payment_method",
            "customer_name",
            "receipt_number",
            "note",
            "customer",
            "cash_amount",
            "momo_amount",
            "pos_amount",
            "credit_amount",
        ]

    def __init__(self, *args, **kwargs):
        self.active_shift = kwargs.pop("active_shift", None)
        super().__init__(*args, **kwargs)

        # Filter pumps by active shift station if provided
        if self.active_shift:
            self.fields["pump"].queryset = Pump.objects.filter(
                station=self.active_shift.station, is_active=True
            ).order_by("label")

        # If pump provided in initial/instance, limit nozzle queryset
        pump = self.initial.get("pump") or (self.instance.pump if self.instance.pk else None)
        if pump:
            self.fields["nozzle"].queryset = Nozzle.objects.filter(pump=pump, is_active=True).order_by("fuel_type")
        else:
            self.fields["nozzle"].queryset = Nozzle.objects.none()

        # readonly helpers
        self.fields["tank_display"].widget.attrs.update(field_classes(readonly=True))
        self.fields["fuel_type_display"].widget.attrs.update(field_classes(readonly=True))
        self.fields["current_stock_display"].widget.attrs.update(field_classes(readonly=True))
        self.fields["active_shift_info"].widget.attrs.update(field_classes(readonly=True))
        self.fields["attendant_info"].widget.attrs.update(field_classes(readonly=True))

    def clean(self):
        cleaned = super().clean()

        pump = cleaned.get("pump")
        nozzle = cleaned.get("nozzle")
        opening = cleaned.get("opening_meter") or Decimal("0")
        closing = cleaned.get("closing_meter")
        volume = cleaned.get("volume_liters")
        unit_price = cleaned.get("unit_price")
        total_amount = cleaned.get("total_amount")
        payment_method = cleaned.get("payment_method")
        customer = cleaned.get("customer")

        # nozzle and pump linkage
        if nozzle is None:
            raise forms.ValidationError("Select a nozzle.")
        if pump and nozzle.pump_id != pump.id:
            raise forms.ValidationError("Selected nozzle does not belong to the chosen pump.")

        # closing meter validation
        if closing is not None and closing < opening:
            raise forms.ValidationError("Closing meter cannot be less than opening meter.")

        # derive volume if meters provided
        if closing is not None and opening is not None:
            volume_calc = quantize_2(closing - opening)
            cleaned["volume_liters"] = volume_calc
            volume = volume_calc

        if volume is None or volume <= 0:
            raise forms.ValidationError("Volume must be greater than zero.")
        if unit_price is None or unit_price <= 0:
            raise forms.ValidationError("Unit price must be greater than zero.")

        # derive total if needed
        if not total_amount:
            total_amount = quantize_2(volume * unit_price)
            cleaned["total_amount"] = total_amount
        else:
            total_amount = quantize_2(total_amount)
            cleaned["total_amount"] = total_amount
        if total_amount <= 0:
            raise forms.ValidationError("Total amount must be greater than zero.")

        # credit requires customer
        if payment_method == FuelSale.PaymentMethod.CREDIT and not customer:
            raise forms.ValidationError("Customer is required for credit sales.")

        # station consistency
        if self.active_shift:
            if nozzle.pump.station_id != self.active_shift.station_id:
                raise forms.ValidationError("Nozzle must belong to the active shift's station.")

        # tank checks
        tank = nozzle.tank
        if not tank:
            raise forms.ValidationError("Selected nozzle is not linked to a tank.")
        if tank.current_volume_liters < volume:
            raise forms.ValidationError("Insufficient stock in the linked tank.")
        return cleaned


class PumpReadingForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.shift = kwargs.pop("shift", None)
        super().__init__(*args, **kwargs)
        if self.shift:
            self.fields["nozzle"].queryset = Nozzle.objects.filter(
                pump__station=self.shift.station, is_active=True
            ).order_by("pump__label", "fuel_type")
        else:
            self.fields["nozzle"].queryset = Nozzle.objects.filter(is_active=True)

        self.fields["nozzle"].widget.attrs.update(field_classes())
        self.fields["opening_reading"].widget.attrs.update(field_classes({"step": "0.01"}))
        self.fields["closing_reading"].widget.attrs.update(field_classes({"step": "0.01"}))
        self.fields["note"].widget.attrs.update(field_classes({"rows": 2}))

    class Meta:
        model = PumpReading
        fields = ["nozzle", "opening_reading", "closing_reading", "note"]

    def clean(self):
        cleaned = super().clean()
        opening = cleaned.get("opening_reading")
        closing = cleaned.get("closing_reading")
        nozzle = cleaned.get("nozzle")
        if closing is not None and opening is not None and closing < opening:
            raise forms.ValidationError("Closing reading cannot be less than opening reading.")
        if self.shift and nozzle and nozzle.pump.station_id != self.shift.station_id:
            raise forms.ValidationError("Nozzle must belong to the shift station.")
        return cleaned


class OMCSalesEntryForm(forms.ModelForm):
    date_input_format = "%Y-%m-%d"

    class Meta:
        model = OMCSalesEntry
        fields = [
            "terminal",
            "omc",
            "product",
            "volume_liters",
            "unit_price",
            "sale_date",
            "submission_reference",
            "remarks",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["sale_date"].widget = forms.DateInput(
            format=self.date_input_format,
            attrs={
                "type": "date",
                "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
            },
        )
        self.fields["sale_date"].input_formats = [self.date_input_format]
        self.fields["remarks"].widget.attrs["rows"] = 3
