from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Dispatch(TimeStampedModel):
    product = models.ForeignKey("products.Product", related_name="dispatches", on_delete=models.PROTECT)
    quantity_dispatched = models.DecimalField(max_digits=14, decimal_places=2)
    terminal = models.ForeignKey("terminals.Terminal", related_name="dispatches", on_delete=models.PROTECT)
    tank = models.ForeignKey("tanks.Tank", related_name="dispatches", on_delete=models.PROTECT)
    omc = models.ForeignKey("omcs.OMC", related_name="dispatches", on_delete=models.PROTECT)
    destination = models.CharField(max_length=255)
    reference_number = models.CharField(max_length=80, unique=True)
    dispatch_date = models.DateField()
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="dispatch_entries",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-dispatch_date", "-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.product.product_name}"

