from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from transport.core.models import TimeStampedModel


class VehicleOwner(TimeStampedModel):
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_account = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "phone"])]

    def __str__(self):
        return self.name


class Vehicle(TimeStampedModel):
    class VehicleStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    class VehicleType(models.TextChoices):
        TRUCK = "TRUCK", "Truck"
        TANKER = "TANKER", "Tanker"
        TRAILER = "TRAILER", "Trailer"
        PICKUP = "PICKUP", "Pickup"
        VAN = "VAN", "Van"
        FLATBED = "FLATBED", "Flatbed"

    class FuelType(models.TextChoices):
        PETROL = "PETROL", "Petrol"
        DIESEL = "DIESEL", "Diesel"
        ELECTRIC = "ELECTRIC", "Electric"
        HYBRID = "HYBRID", "Hybrid"
        OTHER = "OTHER", "Other"

    class OwnershipType(models.TextChoices):
        COMPANY = "company", "Company"
        EXTERNAL = "external", "External"

    # Backward compatibility property
    STATUS_CHOICES = VehicleStatus.choices
    VEHICLE_TYPE_CHOICES = VehicleType.choices

    plate_number = models.CharField(max_length=40, unique=True)
    vehicle_model = models.CharField(max_length=100, blank=True, null=True)
    vehicle_type = models.CharField(max_length=60, choices=VehicleType.choices, default=VehicleType.TRUCK)
    year = models.PositiveIntegerField(blank=True, null=True)
    fuel_type = models.CharField(max_length=50, choices=FuelType.choices, blank=True, null=True)
    engine_capacity = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    capacity = models.DecimalField(max_digits=12, decimal_places=2, help_text="Vehicle load capacity")
    ownership_type = models.CharField(
        max_length=16,
        choices=OwnershipType.choices,
        default=OwnershipType.COMPANY,
    )
    owner = models.ForeignKey(
        "atms_vehicles.VehicleOwner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicles",
    )
    current_odometer = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=16, choices=VehicleStatus.choices, default=VehicleStatus.AVAILABLE)
    insurance_expiry = models.DateField()
    inspection_expiry = models.DateField()
    service_interval_km = models.PositiveIntegerField(default=10000)
    last_service_km = models.PositiveIntegerField(default=0)
    next_service_km = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["plate_number"]
        indexes = [
            models.Index(fields=["status", "insurance_expiry"]),
            models.Index(fields=["inspection_expiry"]),
            models.Index(fields=["ownership_type", "owner"]),
        ]
        permissions = [
            ("manage_vehicles", "Can manage vehicles"),
        ]

    def __str__(self):
        return self.plate_number

    @property
    def load_capacity(self):
        return self.capacity

    def clean(self):
        if self.service_interval_km <= 0:
            raise ValidationError({"service_interval_km": "Service interval must be greater than zero."})
        if self.current_odometer < 0:
            raise ValidationError({"current_odometer": "Current odometer cannot be negative."})
        current_year = timezone.now().year + 1
        if self.year and (self.year < 1950 or self.year > current_year):
            raise ValidationError({"year": f"Year must be between 1950 and {current_year}."})
        if self.ownership_type == self.OwnershipType.EXTERNAL and not self.owner_id and not getattr(self, "_pending_new_owner", False):
            raise ValidationError({"owner": "Owner is required for external vehicles."})
        if self.ownership_type == self.OwnershipType.COMPANY and self.owner_id:
            raise ValidationError({"owner": "Company vehicles should not have an external owner selected."})

    def calculate_next_service_km(self):
        return int(self.last_service_km + self.service_interval_km)

    def can_be_assigned(self):
        today = timezone.now().date()
        if self.status != self.VehicleStatus.AVAILABLE:
            return False, "Vehicle is not available."
        if self.insurance_expiry < today:
            return False, "Vehicle insurance is expired."
        if self.inspection_expiry < today:
            return False, "Vehicle inspection is expired."
        return True, "OK"

    def save(self, *args, **kwargs):
        if self.ownership_type == self.OwnershipType.COMPANY:
            self.owner = None
        self.next_service_km = self.calculate_next_service_km()
        super().save(*args, **kwargs)
