from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from stations.models import Nozzle, Station


DECIMAL_2 = Decimal("0.01")


def quantize_2(value):
    return Decimal(value or 0).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)


class ShiftSession(TimeStampedModel):
    class ShiftType(models.TextChoices):
        MORNING = "morning", "Morning Shift"
        EVENING = "evening", "Evening Shift"
        NIGHT = "night", "Night Shift"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    station = models.ForeignKey(Station, related_name="shifts", on_delete=models.CASCADE)
    attendant = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="attendant_shifts", on_delete=models.SET_NULL, null=True, blank=True
    )
    opened_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="opened_shifts", on_delete=models.SET_NULL, null=True, blank=True
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="closed_shifts", on_delete=models.SET_NULL, null=True, blank=True
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    shift_type = models.CharField(max_length=20, choices=ShiftType.choices, default=ShiftType.MORNING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    note = models.TextField(blank=True)
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_cash = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    total_sales = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_liters = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Cash drawer: expected cash from CASH payment sales only; variance = closing_cash - expected_cash
    expected_cash = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_card_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_mobile_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_credit_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    variance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Cash variance: declared closing cash minus expected cash from cash sales.",
    )
    closing_note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"Shift {self.pk} - {self.station.code} ({self.get_status_display()})"

    def clean(self):
        errors = {}
        if self.status == self.Status.OPEN:
            if not self.station_id:
                errors["station"] = "Station is required."
            elif not self.station.is_active:
                errors["station"] = "Selected station is inactive."
            if not self.attendant_id:
                errors["attendant"] = "Attendant is required."
            if self.attendant_id:
                operational_roles = {"admin", "station_manager", "supervisor", "pump_attendant"}
                if not self.attendant.is_active:
                    errors["attendant"] = "Selected attendant is inactive."
                elif getattr(self.attendant, "role", None) not in operational_roles:
                    errors["attendant"] = "Selected attendant is not operational station staff."
                elif self.station_id and self.attendant.assigned_station_id != self.station_id:
                    errors["attendant"] = "Selected attendant is not assigned to this station."
        if self.status == self.Status.OPEN and self.station_id and self.attendant_id:
            conflicts = ShiftSession.objects.filter(status=self.Status.OPEN)
            if self.pk:
                conflicts = conflicts.exclude(pk=self.pk)
            if conflicts.filter(station_id=self.station_id).exists():
                errors["station"] = "This station already has an open shift."
            if conflicts.filter(attendant_id=self.attendant_id).exists():
                errors["attendant"] = "This attendant already has an open shift."
        if errors:
            raise ValidationError(errors)

    def close(self, closing_cash=None, closed_by=None, closing_note=""):
        from django.db.models import Sum

        if closing_cash is None:
            raise ValidationError({"closing_cash": "Closing amount is required."})
        self.closed_at = timezone.now()
        self.status = self.Status.CLOSED
        self.closing_cash = closing_cash
        sales_qs = self.sales.all()
        totals = sales_qs.aggregate(sum_amt=Sum("total_amount"), sum_vol=Sum("volume_liters"))
        self.total_sales = totals.get("sum_amt") or 0
        self.total_liters = totals.get("sum_vol") or 0

        cash_agg = sales_qs.filter(payment_method=FuelSale.PaymentMethod.CASH).aggregate(s=Sum("total_amount"))
        card_agg = sales_qs.filter(payment_method=FuelSale.PaymentMethod.CARD).aggregate(s=Sum("total_amount"))
        mobile_agg = sales_qs.filter(payment_method=FuelSale.PaymentMethod.MOBILE).aggregate(s=Sum("total_amount"))
        credit_agg = sales_qs.filter(payment_method=FuelSale.PaymentMethod.CREDIT).aggregate(s=Sum("total_amount"))

        self.expected_cash = Decimal(cash_agg.get("s") or 0)
        self.closing_card_total = Decimal(card_agg.get("s") or 0)
        self.closing_mobile_total = Decimal(mobile_agg.get("s") or 0)
        self.closing_credit_total = Decimal(credit_agg.get("s") or 0)
        self.variance_amount = Decimal(self.closing_cash or 0) - self.expected_cash

        self.closing_note = closing_note or ""
        if closed_by:
            self.closed_by = closed_by
        self.full_clean()
        self.save(update_fields=[
            "closed_at",
            "status",
            "closing_cash",
            "total_sales",
            "total_liters",
            "expected_cash",
            "closing_card_total",
            "closing_mobile_total",
            "closing_credit_total",
            "variance_amount",
            "closing_note",
            "closed_by",
            "updated_at",
        ])
        return self


class PumpReading(TimeStampedModel):
    shift = models.ForeignKey(ShiftSession, related_name="pump_readings", on_delete=models.CASCADE)
    nozzle = models.ForeignKey(Nozzle, related_name="readings", on_delete=models.CASCADE)
    opening_reading = models.DecimalField(max_digits=12, decimal_places=2)
    closing_reading = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ("shift", "nozzle")
        ordering = ["nozzle__pump__station__name", "nozzle__pump__label"]

    def __str__(self):
        return f"{self.nozzle} ({self.shift_id})"

    def clean(self):
        if self.nozzle and self.shift and self.nozzle.pump.station_id != self.shift.station_id:
            raise ValidationError("Nozzle must belong to the same station as the shift.")
        if self.closing_reading and self.closing_reading < self.opening_reading:
            raise ValidationError("Closing reading cannot be less than opening reading.")

    @property
    def total_liters(self):
        if self.closing_reading is None:
            return None
        return self.closing_reading - self.opening_reading


class FuelSale(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        MOBILE = "mobile", "Mobile Money"
        CREDIT = "credit", "Customer Credit"

    shift = models.ForeignKey(ShiftSession, related_name="sales", on_delete=models.CASCADE)
    attendant = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="sales_made", on_delete=models.SET_NULL, null=True, blank=True
    )
    pump = models.ForeignKey("stations.Pump", related_name="sales", on_delete=models.SET_NULL, null=True, blank=True)
    tank = models.ForeignKey("inventory.FuelTank", related_name="sales", on_delete=models.SET_NULL, null=True, blank=True)
    nozzle = models.ForeignKey(Nozzle, related_name="sales", on_delete=models.CASCADE)
    opening_meter = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    closing_meter = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    volume_liters = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    customer_name = models.CharField(max_length=120, blank=True)
    receipt_number = models.CharField(max_length=50, blank=True)
    inventory_posted = models.BooleanField(default=False)
    inventory_posted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sale {self.total_amount} {self.get_payment_method_display()}"

    def clean(self):
        if self.nozzle is None:
            raise ValidationError("Select a nozzle for this sale.")
        if self.shift and self.nozzle and self.nozzle.pump.station_id != self.shift.station_id:
            raise ValidationError("Nozzle must belong to the same station as the shift.")
        if not self.nozzle.tank_id:
            raise ValidationError("Selected nozzle is not linked to a tank.")
        if self.nozzle.tank and self.nozzle.tank.fuel_type != self.nozzle.fuel_type:
            raise ValidationError("Nozzle fuel type must match its tank fuel type.")
        if self.pump_id and self.nozzle and self.pump_id != self.nozzle.pump_id:
            raise ValidationError("Selected pump must match the nozzle's pump.")
        if self.tank_id and self.nozzle and self.nozzle.tank_id and self.tank_id != self.nozzle.tank_id:
            raise ValidationError("Selected tank must match the nozzle's tank.")
        if self.closing_meter and self.closing_meter < self.opening_meter:
            raise ValidationError("Closing meter cannot be less than opening meter.")
        if self.volume_liters is not None and self.volume_liters < 0:
            raise ValidationError("Volume cannot be negative.")

    def _compute_volume(self):
        """Compute volume from meter readings if possible."""
        if self.closing_meter is not None:
            return self.closing_meter - self.opening_meter
        return self.volume_liters

    def save(self, *args, **kwargs):
        if self.pk:
            original = (
                FuelSale.objects.filter(pk=self.pk)
                .only("inventory_posted", "nozzle_id", "tank_id", "opening_meter", "closing_meter", "volume_liters")
                .first()
            )
            if original and original.inventory_posted:
                critical_changed = any(
                    [
                        original.nozzle_id != self.nozzle_id,
                        original.tank_id != self.tank_id,
                        quantize_2(original.opening_meter) != quantize_2(self.opening_meter),
                        quantize_2(original.closing_meter) != quantize_2(self.closing_meter),
                        quantize_2(original.volume_liters) != quantize_2(self.volume_liters),
                    ]
                )
                if critical_changed:
                    raise ValidationError(
                        "Posted sales cannot be edited directly because inventory has already been updated."
                    )

        computed_volume = self._compute_volume()
        if computed_volume is not None:
            self.volume_liters = quantize_2(computed_volume)
        if self.opening_meter is not None:
            self.opening_meter = quantize_2(self.opening_meter)
        if self.closing_meter is not None:
            self.closing_meter = quantize_2(self.closing_meter)
        if self.unit_price is not None:
            self.unit_price = quantize_2(self.unit_price)
        if self.volume_liters and self.unit_price and (not self.total_amount):
            self.total_amount = quantize_2(self.volume_liters * self.unit_price)
        elif self.total_amount is not None:
            self.total_amount = quantize_2(self.total_amount)

        if self.nozzle_id:
            if not self.pump_id:
                self.pump_id = self.nozzle.pump_id
            if self.nozzle.tank_id and not self.tank_id:
                self.tank_id = self.nozzle.tank_id

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.inventory_posted and self.tank_id and self.volume_liters:
            from inventory.models import InventoryRecord

            reference = f"Sale reversal #{self.pk} - deleted sale"
            self.tank.adjust_stock(
                quantize_2(self.volume_liters),
                reference=reference,
                change_type=InventoryRecord.ChangeType.IN,
                movement_type=InventoryRecord.MovementType.REVERSAL,
                performed_by=self.attendant,
                notes="Tank stock restored because a posted sale was deleted.",
            )
        return super().delete(*args, **kwargs)


class Customer(TimeStampedModel):
    class CustomerType(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        COMPANY = "company", "Company"
        CREDIT = "credit", "Credit"

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    customer_type = models.CharField(max_length=20, choices=CustomerType.choices, default=CustomerType.WALK_IN)
    is_credit_allowed = models.BooleanField(default=False)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class CreditTransaction(TimeStampedModel):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially Paid"
        PAID = "paid", "Paid"

    customer = models.ForeignKey(Customer, related_name="credit_transactions", on_delete=models.CASCADE)
    sale = models.ForeignKey("FuelSale", related_name="credit_transactions", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UNPAID)

    class Meta:
        ordering = ["-created_at"]

    @property
    def outstanding_amount(self):
        return max(Decimal("0"), quantize_2(self.amount) - quantize_2(self.amount_paid))


class CreditPayment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        MOBILE = "mobile", "Mobile Money"
        BANK = "bank", "Bank Transfer"

    customer = models.ForeignKey(Customer, related_name="credit_payments", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=60, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="credit_payments_received",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Credit payment {self.amount} for {self.customer}"
