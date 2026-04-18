from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class ProductReceipt(TimeStampedModel):
    supplier = models.ForeignKey("products.Supplier", related_name="receipts", on_delete=models.PROTECT)
    product = models.ForeignKey("products.Product", related_name="receipts", on_delete=models.PROTECT)
    quantity_received = models.DecimalField(max_digits=14, decimal_places=2)
    terminal = models.ForeignKey("terminals.Terminal", related_name="receipts", on_delete=models.PROTECT)
    tank = models.ForeignKey("tanks.Tank", related_name="receipts", on_delete=models.PROTECT)
    reference_number = models.CharField(max_length=80, unique=True)
    receipt_date = models.DateField()
    remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="product_receipts",
        on_delete=models.SET_NULL,
    )

    class Meta:
        ordering = ["-receipt_date", "-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.product.product_name}"

