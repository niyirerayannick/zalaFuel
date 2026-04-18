from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Terminal(TimeStampedModel):
    class Status(models.TextChoices):
        OPERATIONAL = "operational", "Operational"
        MAINTENANCE = "maintenance", "Maintenance"
        RESTRICTED = "restricted", "Restricted"
        OFFLINE = "offline", "Offline"

    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=30, unique=True)
    location = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPERATIONAL)
    capacity_liters = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="managed_terminals",
        on_delete=models.SET_NULL,
    )
    manager_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.manager_id:
            self.manager_name = self.manager.full_name
        super().save(*args, **kwargs)


class TerminalActivityLog(TimeStampedModel):
    terminal = models.ForeignKey(Terminal, related_name="activity_logs", on_delete=models.CASCADE)
    action = models.CharField(max_length=80)
    description = models.TextField()
    event_time = models.DateTimeField()

    class Meta:
        ordering = ["-event_time", "-created_at"]

    def __str__(self):
        return f"{self.terminal.name} - {self.action}"
