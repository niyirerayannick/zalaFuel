from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CommodityType(TimeStampedModel):
    class Code(models.TextChoices):
        FUEL = "FUEL", "Fuel"
        GOODS = "GOODS", "Goods"

    code = models.CharField(max_length=16, choices=Code.choices, unique=True)
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["code", "is_active"])]

    def __str__(self):
        return self.name


class TransportRate(TimeStampedModel):
    route = models.ForeignKey("atms_routes.Route", on_delete=models.CASCADE, related_name="rates")
    commodity_type = models.ForeignKey("atms_core.CommodityType", on_delete=models.PROTECT, related_name="rates")
    rate_per_km = models.DecimalField(max_digits=12, decimal_places=2)
    minimum_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["route__origin", "route__destination"]
        unique_together = ("route", "commodity_type")
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self):
        return f"{self.route} - {self.commodity_type.name}"
