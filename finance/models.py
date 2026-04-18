from django.conf import settings
from django.db import models

from core.models import TimeStampedModel
from stations.models import Station


class CustomerAccount(TimeStampedModel):
    """AR / invoicing customer; optional link to POS ``sales.Customer`` for balance sync."""

    sales_customer = models.OneToOneField(
        "sales.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_customer_account",
    )
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Invoice(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    customer = models.ForeignKey(CustomerAccount, related_name="invoices", on_delete=models.CASCADE)
    station = models.ForeignKey(Station, related_name="invoices", on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice {self.reference}"


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        MOBILE = "mobile", "Mobile Money"
        BANK = "bank", "Bank Transfer"

    invoice = models.ForeignKey(Invoice, related_name="payments", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.CASH)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="payments_received", on_delete=models.SET_NULL, null=True, blank=True
    )
    reference = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.amount} {self.method}"


class Receipt(TimeStampedModel):
    payment = models.OneToOneField(Payment, related_name="receipt", on_delete=models.CASCADE)
    receipt_number = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.receipt_number
