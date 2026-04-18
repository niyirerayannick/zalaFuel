from django.db import models

from core.models import TimeStampedModel


class Alert(TimeStampedModel):
    class AlertType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock"
        VARIANCE = "variance", "Variance Alert"
        MISSING_SUBMISSION = "missing_submission", "Missing Submission"
        ABNORMAL_CHANGE = "abnormal_change", "Abnormal Change"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    severity = models.CharField(max_length=20, choices=Severity.choices, default=Severity.WARNING)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    title = models.CharField(max_length=150)
    message = models.TextField()
    terminal = models.ForeignKey("terminals.Terminal", null=True, blank=True, related_name="alerts", on_delete=models.SET_NULL)
    tank = models.ForeignKey("tanks.Tank", null=True, blank=True, related_name="alerts", on_delete=models.SET_NULL)
    product = models.ForeignKey("products.Product", null=True, blank=True, related_name="alerts", on_delete=models.SET_NULL)
    omc = models.ForeignKey("omcs.OMC", null=True, blank=True, related_name="alerts", on_delete=models.SET_NULL)
    triggered_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-triggered_at", "-created_at"]

    def __str__(self):
        return self.title

