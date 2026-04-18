from django.conf import settings
from django.db import models

from transport.core.models import TimeStampedModel


class Customer(TimeStampedModel):
    class CustomerStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        SUSPENDED = "SUSPENDED", "Suspended"

    # Backward compatibility property
    STATUS_CHOICES = CustomerStatus.choices

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_profile'
    )
    company_name = models.CharField(max_length=255, db_index=True)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=CustomerStatus.choices, default=CustomerStatus.ACTIVE)
    is_active = models.BooleanField(default=True)  # Keep for backward compatibility

    class Meta:
        ordering = ["company_name"]
        permissions = [
            ("manage_customers", "Can manage customers"),
        ]

    def __str__(self):
        return self.company_name
