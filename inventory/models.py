from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel
from stations.models import Station


class InventoryRecord(TimeStampedModel):
    class ChangeType(models.TextChoices):
        IN = "IN", "Stock In"
        OUT = "OUT", "Stock Out"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    class MovementType(models.TextChoices):
        DELIVERY = "delivery", "Incoming Delivery"
        SALE = "sale", "Sale"
        ADJUSTMENT = "adjustment", "Adjustment"
        REVERSAL = "reversal", "Reversal"

    tank = models.ForeignKey("inventory.FuelTank", related_name="inventory_records", on_delete=models.CASCADE)
    change_type = models.CharField(max_length=20, choices=ChangeType.choices, default=ChangeType.ADJUSTMENT)
    movement_type = models.CharField(max_length=30, choices=MovementType.choices, default=MovementType.ADJUSTMENT)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    reference = models.CharField(max_length=255, blank=True)
    supplier = models.ForeignKey(
        "suppliers.Supplier",
        related_name="inventory_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    delivery_receipt = models.ForeignKey(
        "suppliers.DeliveryReceipt",
        related_name="inventory_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="inventory_records",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tank} {self.change_type} {self.quantity}"


class FuelTank(TimeStampedModel):
    class FuelType(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"

    station = models.ForeignKey(Station, related_name="tanks", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices)
    capacity_liters = models.DecimalField(max_digits=12, decimal_places=2)
    current_volume_liters = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_level_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("station", "name")
        ordering = ["station__name", "name"]

    def __str__(self):
        return f"{self.station.code} - {self.name}"

    def is_below_threshold(self):
        return bool(self.low_level_threshold and self.current_volume_liters <= self.low_level_threshold)

    @property
    def percent_full(self):
        if not self.capacity_liters:
            return 0
        return float((self.current_volume_liters or 0) / self.capacity_liters * 100)

    def adjust_stock(
        self,
        delta,
        reference="",
        change_type=InventoryRecord.ChangeType.ADJUSTMENT,
        movement_type=InventoryRecord.MovementType.ADJUSTMENT,
        supplier=None,
        delivery_receipt=None,
        performed_by=None,
        unit_cost=None,
        notes="",
    ):
        """Atomically update stock and log an inventory record."""
        from django.db import transaction

        with transaction.atomic():
            locked_tank = FuelTank.objects.select_for_update().get(pk=self.pk)
            delta = Decimal(delta)
            new_level = (locked_tank.current_volume_liters or Decimal("0")) + delta
            if new_level < 0:
                raise ValidationError("Insufficient stock in tank.")
            if locked_tank.capacity_liters and new_level > locked_tank.capacity_liters:
                raise ValidationError("Stock update exceeds tank capacity.")

            locked_tank.current_volume_liters = new_level
            locked_tank.save(update_fields=["current_volume_liters", "updated_at"])
            InventoryRecord.objects.create(
                tank=locked_tank,
                change_type=InventoryRecord.ChangeType(change_type),
                movement_type=InventoryRecord.MovementType(movement_type),
                quantity=delta,
                balance_after=new_level,
                reference=reference,
                supplier=supplier,
                delivery_receipt=delivery_receipt,
                performed_by=performed_by,
                unit_cost=unit_cost,
                notes=notes or "",
            )
            self.current_volume_liters = locked_tank.current_volume_liters

        # Placeholder for low stock notifications
        return self.current_volume_liters


class TankDipReading(TimeStampedModel):
    class Method(models.TextChoices):
        MANUAL = "manual", "Manual Dip"
        ATG = "atg", "Automatic Tank Gauge"

    tank = models.ForeignKey(FuelTank, related_name="readings", on_delete=models.CASCADE)
    reading_time = models.DateTimeField(auto_now_add=True)
    volume_liters = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.MANUAL)
    measured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tank_readings"
    )

    class Meta:
        ordering = ["-reading_time"]

    def __str__(self):
        return f"{self.tank} @ {self.reading_time:%Y-%m-%d %H:%M}"


class StockReconciliation(TimeStampedModel):
    tank = models.ForeignKey(FuelTank, related_name="reconciliations", on_delete=models.CASCADE)
    shift = models.ForeignKey(
        "sales.ShiftSession", related_name="reconciliations", on_delete=models.SET_NULL, null=True, blank=True
    )
    expected_volume = models.DecimalField(max_digits=12, decimal_places=2)
    actual_volume = models.DecimalField(max_digits=12, decimal_places=2)
    variance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.variance = (self.actual_volume or 0) - (self.expected_volume or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reconciliation {self.tank} ({self.created_at:%Y-%m-%d})"
