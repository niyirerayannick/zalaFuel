from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from inventory.models import FuelTank
from stations.models import Station


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class FuelPurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ORDERED = "ordered", "Ordered"
        DELIVERED = "delivered", "Delivered"

    supplier = models.ForeignKey(Supplier, related_name="purchase_orders", on_delete=models.CASCADE)
    station = models.ForeignKey(Station, related_name="purchase_orders", on_delete=models.CASCADE)
    fuel_type = models.CharField(
        max_length=20,
        choices=FuelTank.FuelType.choices,
        default=FuelTank.FuelType.DIESEL,
    )
    volume_liters = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    expected_delivery_date = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=50, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PO {self.reference}"


class DeliveryReceipt(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    purchase_order = models.ForeignKey(FuelPurchaseOrder, related_name="deliveries", on_delete=models.CASCADE)
    tank = models.ForeignKey(FuelTank, related_name="deliveries", on_delete=models.SET_NULL, null=True, blank=True)
    delivered_volume = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    delivery_reference = models.CharField(max_length=80, blank=True)
    delivery_date = models.DateField(default=timezone.localdate)
    document = models.FileField(upload_to="deliveries/", blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="deliveries_received"
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Delivery for {self.purchase_order.reference}"

    @property
    def supplier(self):
        return self.purchase_order.supplier

    @property
    def station(self):
        return self.purchase_order.station

    @property
    def fuel_type(self):
        return self.purchase_order.fuel_type

    def clean(self):
        errors = {}
        if not self.purchase_order_id:
            errors["purchase_order"] = "Purchase order is required."
        if self.status != self.Status.CANCELLED:
            if not self.tank_id:
                errors["tank"] = "Tank is required."
            if self.delivered_volume is None or self.delivered_volume <= 0:
                errors["delivered_volume"] = "Received liters must be greater than zero."
        if self.purchase_order_id and self.tank_id:
            if self.tank.station_id != self.purchase_order.station_id:
                errors["tank"] = "Selected tank must belong to the same station as the purchase order."
            if self.tank.fuel_type != self.purchase_order.fuel_type:
                errors["tank"] = "Selected tank fuel type must match the delivery fuel type."
        if self.status == self.Status.RECEIVED and self.posted_at is None:
            errors["status"] = "Received deliveries must be posted through the receiving workflow."
        if errors:
            raise ValidationError(errors)
