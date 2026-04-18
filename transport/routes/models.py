from django.db import models

from transport.core.models import TimeStampedModel


class Route(TimeStampedModel):
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    distance_km = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["origin", "destination"]
        constraints = [
            models.UniqueConstraint(fields=["origin", "destination"], name="atms_unique_route")
        ]
        indexes = [models.Index(fields=["origin", "destination", "is_active"])]

    def __str__(self):
        return f"{self.origin} -> {self.destination}"
