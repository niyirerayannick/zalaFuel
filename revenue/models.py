from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class RevenueEntry(TimeStampedModel):
    terminal = models.ForeignKey("terminals.Terminal", related_name="revenue_entries", on_delete=models.PROTECT)
    product = models.ForeignKey("products.Product", related_name="revenue_entries", on_delete=models.PROTECT)
    omc = models.ForeignKey("omcs.OMC", related_name="revenue_entries", on_delete=models.PROTECT)
    volume_liters = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    revenue_date = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="revenue_entries",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-revenue_date", "-created_at"]

    def __str__(self):
        return f"{self.omc.name} - {self.amount}"

