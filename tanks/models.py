from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel


class Tank(TimeStampedModel):
    terminal = models.ForeignKey("terminals.Terminal", related_name="tanks", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", related_name="tanks", on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    code = models.CharField(max_length=30, unique=True)
    capacity_liters = models.DecimalField(max_digits=14, decimal_places=2)
    current_stock_liters = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    minimum_threshold = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["terminal__name", "name"]
        unique_together = ("terminal", "name")

    def __str__(self):
        return f"{self.terminal.name} - {self.name}"

    @property
    def utilization_percent(self):
        if not self.capacity_liters:
            return Decimal("0")
        return (Decimal(self.current_stock_liters or 0) / Decimal(self.capacity_liters)) * Decimal("100")


class TankStockEntry(TimeStampedModel):
    tank = models.ForeignKey(Tank, related_name="stock_entries", on_delete=models.CASCADE)
    entry_date = models.DateField()
    opening_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_in = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    stock_out = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    closing_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    computed_stock = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    variance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    remarks = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="tank_stock_entries",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        unique_together = ("tank", "entry_date")

    def clean(self):
        if self.closing_stock and self.closing_stock > self.tank.capacity_liters:
            raise ValidationError({"closing_stock": "Closing stock cannot exceed tank capacity."})

    def save(self, *args, **kwargs):
        self.computed_stock = Decimal(self.opening_stock or 0) + Decimal(self.stock_in or 0) - Decimal(self.stock_out or 0)
        self.variance = Decimal(self.closing_stock or 0) - Decimal(self.computed_stock or 0)
        super().save(*args, **kwargs)
        Tank.objects.filter(pk=self.tank_id).update(current_stock_liters=self.closing_stock)

