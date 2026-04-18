from django.conf import settings
from django.db import models
from django.utils import timezone

from transport.core.models import TimeStampedModel


class Driver(TimeStampedModel):
    class WorkStatus(models.TextChoices):
        COMPANY = "COMPANY", "Company Driver"
        EXTERNAL = "EXTERNAL", "External Driver"

    class DriverStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"
        LEAVE = "LEAVE", "Leave"

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        OFF_DUTY = "OFF_DUTY", "Off Duty"
        LEAVE = "LEAVE", "Leave"

    class LicenseCategory(models.TextChoices):
        A = "A", "A - Motorcycles"
        B1 = "B1", "B1 - Light Vehicles"
        B = "B", "B - Standard Vehicles"
        C = "C", "C - Heavy Vehicles"
        D1 = "D1", "D1 - Minibuses"
        D = "D", "D - Buses"
        E = "E", "E - Trailers"
        F = "F", "F - Special Vehicles"

    # Backward compatibility property
    STATUS_CHOICES = DriverStatus.choices
    LICENSE_CATEGORY_CHOICES = LicenseCategory.choices

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_profile',
        help_text="Legacy link only. Drivers do not log in to the system.",
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=32)
    license_number = models.CharField(max_length=80, unique=True)
    license_category = models.CharField(
        max_length=16,
        choices=LicenseCategory.choices,
        default=LicenseCategory.B
    )
    license_expiry = models.DateField()
    license_photo = models.ImageField(
        upload_to='drivers/licenses/',
        blank=True,
        null=True,
        help_text='Upload a photo of the driving license'
    )
    work_status = models.CharField(
        max_length=16,
        choices=WorkStatus.choices,
        default=WorkStatus.COMPANY,
    )
    status = models.CharField(max_length=16, choices=DriverStatus.choices, default=DriverStatus.AVAILABLE)
    assigned_vehicle = models.ForeignKey(
        "atms_vehicles.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_drivers",
    )
    availability_status = models.CharField(
        max_length=16,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status", "license_expiry"]),
            models.Index(fields=["license_number"]),
        ]
        permissions = [
            ("manage_drivers", "Can manage drivers"),
        ]

    def __str__(self):
        return self.name

    def can_be_assigned(self):
        if self.status != self.DriverStatus.AVAILABLE:
            return False, "Driver is not available."
        if self.availability_status != self.AvailabilityStatus.AVAILABLE:
            return False, "Driver availability status does not allow assignment."
        if self.license_expiry < timezone.now().date():
            return False, "Driver license is expired."
        return True, "OK"
