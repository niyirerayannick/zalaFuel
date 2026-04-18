from django.db import models

from core.models import TimeStampedModel


class MarketShareSnapshot(TimeStampedModel):
    snapshot_date = models.DateField()
    omc = models.ForeignKey("omcs.OMC", related_name="market_snapshots", on_delete=models.CASCADE)
    product = models.ForeignKey("products.Product", related_name="market_snapshots", on_delete=models.CASCADE)
    volume_liters = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    revenue_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    market_share_percent = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    class Meta:
        ordering = ["-snapshot_date", "-market_share_percent"]
        unique_together = ("snapshot_date", "omc", "product")

    def __str__(self):
        return f"{self.omc.name} - {self.snapshot_date}"

