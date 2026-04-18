from django.db import models

from core.models import TimeStampedModel


class Supplier(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    supplier_name = models.CharField(max_length=150, unique=True, verbose_name="Supplier Name")
    supplier_code = models.CharField(max_length=30, unique=True, verbose_name="Supplier Code")
    contact_person = models.CharField(max_length=120, blank=True, verbose_name="Contact Person")
    phone = models.CharField(max_length=40, blank=True, verbose_name="Phone")
    email = models.EmailField(blank=True, verbose_name="Email")
    address = models.TextField(blank=True, verbose_name="Address")
    country = models.CharField(max_length=100, blank=True, verbose_name="Country")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, verbose_name="Status")

    class Meta:
        ordering = ["supplier_name"]

    def __str__(self):
        return self.supplier_name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Product(TimeStampedModel):
    class ProductType(models.TextChoices):
        PMS = "pms", "Premium Motor Spirit (PMS)"
        AGO = "ago", "Automotive Gas Oil (AGO)"
        DPK = "dpk", "Dual Purpose Kerosene (DPK)"
        LPG = "lpg", "Liquefied Petroleum Gas (LPG)"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    product_name = models.CharField(max_length=120, unique=True, verbose_name="Product Name")
    product_code = models.CharField(max_length=30, unique=True, verbose_name="Product Code")
    product_type = models.CharField(max_length=20, choices=ProductType.choices, default=ProductType.PMS, verbose_name="Product Type")
    unit_of_measure = models.CharField(max_length=20, default="Liters", verbose_name="Unit of Measure")
    description = models.TextField(blank=True, verbose_name="Description")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, verbose_name="Status")
    density = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True, verbose_name="Density (kg/m³)")
    temperature_factor = models.DecimalField(max_digits=8, decimal_places=6, null=True, blank=True, verbose_name="Temperature Factor")
    color_marker = models.CharField(max_length=20, blank=True, verbose_name="Color Marker")
    display_order = models.PositiveIntegerField(default=0, verbose_name="Display Order")

    class Meta:
        ordering = ["display_order", "product_name"]

    def __str__(self):
        return self.product_name

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

