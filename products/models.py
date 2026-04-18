from django.db import models

from core.models import TimeStampedModel


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    source_location = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(TimeStampedModel):
    class Category(models.TextChoices):
        PMS = "pms", "PMS"
        AGO = "ago", "AGO"
        DPK = "dpk", "DPK"
        LPG = "lpg", "LPG"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=30, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.PMS)
    unit = models.CharField(max_length=20, default="Liters")
    default_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

