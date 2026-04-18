from django.conf import settings
from django.db import models

from django.core.exceptions import ValidationError

from core.models import TimeStampedModel


class Station(TimeStampedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=20, unique=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_stations",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def _generate_code(self):
        prefix = "STN-"
        last = (
            Station.objects.filter(code__startswith=prefix)
            .order_by("-code")
            .values_list("code", flat=True)
            .first()
        )
        if last:
            try:
                num = int(last.replace(prefix, ""))
            except ValueError:
                num = 0
        else:
            num = 0
        return f"{prefix}{num + 1:04d}"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._generate_code()
        super().save(*args, **kwargs)


class Pump(TimeStampedModel):
    station = models.ForeignKey(Station, related_name="pumps", on_delete=models.CASCADE)
    label = models.CharField(max_length=50)
    tank = models.ForeignKey(
        "inventory.FuelTank", related_name="pumps", on_delete=models.SET_NULL, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("station", "label")
        ordering = ["station__name", "label"]

    def __str__(self):
        return f"{self.station.code} - {self.label}"


class Nozzle(TimeStampedModel):
    class FuelType(models.TextChoices):
        PETROL = "petrol", "Petrol"
        DIESEL = "diesel", "Diesel"

    pump = models.ForeignKey(Pump, related_name="nozzles", on_delete=models.CASCADE)
    fuel_type = models.CharField(max_length=20, choices=FuelType.choices)
    tank = models.ForeignKey(
        "inventory.FuelTank", related_name="nozzles", on_delete=models.PROTECT, null=True, blank=True
    )
    meter_start = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    meter_end = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pump__station__name", "pump__label", "fuel_type"]

    def __str__(self):
        return f"{self.pump} - {self.get_fuel_type_display()}"

    def clean(self):
        if self.tank and self.pump and self.tank.station_id != self.pump.station_id:
            raise ValidationError("Nozzle tank must belong to the same station as the pump.")
        if self.tank and self.fuel_type and self.tank.fuel_type != self.fuel_type:
            raise ValidationError("Tank fuel type must match nozzle fuel type.")
