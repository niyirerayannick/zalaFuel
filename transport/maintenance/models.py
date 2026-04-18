from decimal import Decimal

from django.conf import settings
from django.db import models

from transport.core.models import TimeStampedModel
from transport.vehicles.models import Vehicle


def default_service_types():
    return [
        "Oil Change",
        "Brake Service",
        "Tire Replacement",
        "Engine Service",
        "Suspension Repair",
        "Battery Replacement",
        "Transmission Service",
        "Welding",
        "Preventive Maintenance",
        "General Inspection",
    ]


class MaintenanceRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    vehicle = models.ForeignKey("atms_vehicles.Vehicle", on_delete=models.CASCADE, related_name="maintenance_records")
    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.SET_NULL, null=True, blank=True, related_name="maintenance_records")
    service_type = models.CharField(max_length=80)
    service_date = models.DateField()
    service_km = models.PositiveIntegerField()
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    workshop = models.CharField(max_length=255)
    downtime_days = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_records_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    expense = models.OneToOneField(
        "atms_finance.Expense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_record",
    )

    class Meta:
        ordering = ["-service_date"]
        indexes = [
            models.Index(fields=["vehicle", "service_date"]),
            models.Index(fields=["status", "service_date"]),
        ]

    def __str__(self):
        return f"{self.vehicle.plate_number} - {self.service_type}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.status == self.Status.APPROVED and self.service_km >= self.vehicle.last_service_km:
            self.vehicle.last_service_km = self.service_km
            self.vehicle.status = Vehicle.VehicleStatus.MAINTENANCE if self.downtime_days > 0 else Vehicle.VehicleStatus.AVAILABLE
            self.vehicle.save(update_fields=["last_service_km", "next_service_km", "status", "updated_at"])

    @property
    def maintenance_cost_per_km(self):
        if self.service_km <= 0:
            return Decimal("0")
        return self.cost / Decimal(self.service_km)
