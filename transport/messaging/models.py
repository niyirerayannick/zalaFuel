import logging

from django.conf import settings
from django.db import models

from transport.core.models import TimeStampedModel

logger = logging.getLogger(__name__)


class WhatsAppMessage(TimeStampedModel):
    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"
        FAILED = "failed", "Failed"

    phone_number = models.CharField(max_length=32, db_index=True)
    message = models.TextField()
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        default=Direction.INCOMING,
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.RECEIVED,
    )
    related_trip = models.ForeignKey(
        "atms_trips.Trip",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_messages",
    )
    twilio_sid = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone_number", "direction"]),
        ]

    def __str__(self):
        return f"{self.get_direction_display()} - {self.phone_number} - {self.created_at:%Y-%m-%d %H:%M}"


class NotificationLog(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="whatsapp_notifications",
    )
    phone_number = models.CharField(max_length=32)
    message = models.TextField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    twilio_sid = models.CharField(max_length=64, blank=True)
    error_detail = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification -> {self.phone_number} - {self.status}"


class FuelRequest(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    driver = models.ForeignKey(
        "atms_drivers.Driver",
        on_delete=models.CASCADE,
        related_name="fuel_requests",
    )
    trip = models.ForeignKey(
        "atms_trips.Trip",
        on_delete=models.CASCADE,
        related_name="fuel_requests",
    )
    liters_requested = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_fuel_requests",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Fuel {self.liters_requested}L - {self.trip.order_number} - {self.status}"


class DriverManagerMessage(TimeStampedModel):
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_conversations",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="driver_messages_sent",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="driver_messages_received",
    )
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["driver", "created_at"]),
        ]

    def __str__(self):
        return f"{self.sender} -> {self.recipient or 'Manager'}"
