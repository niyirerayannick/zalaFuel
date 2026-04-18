from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal

from transport.core.models import TimeStampedModel


class ExpenseType(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "is_active"])]

    def __str__(self):
        return self.name


def ensure_default_expense_types():
    maintenance_type = ExpenseType.objects.filter(name="Maintenance").first()
    repairs_type = ExpenseType.objects.filter(name="Repairs").first()
    if repairs_type and not maintenance_type:
        repairs_type.name = "Maintenance"
        repairs_type.is_active = True
        repairs_type.save(update_fields=["name", "is_active", "updated_at"])

    ExpenseType.objects.filter(name__in=["Tolls"]).update(is_active=False)

    defaults = [
        "Fuel",
        "Driver Allowance",
        "Vehicle Rent",
        "Loading",
        "Offloading",
        "Parking",
        "Maintenance",
        "Road Tolls",
        "Miscellaneous",
        "Other Expense",
    ]
    for name in defaults:
        expense_type, created = ExpenseType.objects.get_or_create(name=name, defaults={"is_active": True})
        if not created and not expense_type.is_active:
            expense_type.is_active = True
            expense_type.save(update_fields=["is_active", "updated_at"])


class RevenueType(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "is_active"])]

    def __str__(self):
        return self.name


class Payment(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIAL = "PARTIAL", "Partial"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        BANK = "BANK", "Bank Transfer"
        MOBILE = "MOBILE", "Mobile Money"
        CARD = "CARD", "Card"
        OTHER = "OTHER", "Other"

    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    order = models.ForeignKey("atms_orders.Order", on_delete=models.CASCADE, related_name="payments", null=True, blank=True)
    customer = models.ForeignKey("atms_customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    payment_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=16, choices=PaymentMethod.choices, default=PaymentMethod.BANK)
    reference = models.CharField(max_length=120, blank=True)
    proof_document = models.FileField(upload_to="finance/payments/proofs/%Y/%m/", blank=True)
    notes = models.TextField(blank=True)
    failure_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        indexes = [models.Index(fields=["trip", "payment_date"])]

    def __str__(self):
        return f"{self.trip.order_number if self.trip else 'Manual Revenue'} - {self.amount}"

    @property
    def collected_amount(self):
        if self.status == self.Status.PAID:
            return self.amount or Decimal("0")
        if self.status == self.Status.PARTIAL:
            return self.amount_paid or Decimal("0")
        return Decimal("0")

    @property
    def outstanding_amount(self):
        if self.status == self.Status.PAID:
            return Decimal("0")
        if self.status == self.Status.PARTIAL:
            balance = (self.amount or Decimal("0")) - (self.amount_paid or Decimal("0"))
            return balance if balance > 0 else Decimal("0")
        return self.amount or Decimal("0")

    def save(self, *args, **kwargs):
        self.amount_paid = self.amount_paid or Decimal("0")
        if self.status == self.Status.PAID:
            self.amount_paid = self.amount or Decimal("0")
            self.failure_reason = ""
        elif self.status == self.Status.PENDING:
            self.amount_paid = Decimal("0")
            self.failure_reason = ""
        elif self.status == self.Status.FAILED:
            self.amount_paid = Decimal("0")
        else:
            self.failure_reason = ""
        super().save(*args, **kwargs)


class Expense(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        PAID = "PAID", "Paid"
        REJECTED = "REJECTED", "Rejected"

    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    vehicle = models.ForeignKey("atms_vehicles.Vehicle", on_delete=models.SET_NULL, null=True, blank=True, related_name="finance_expenses")
    type = models.ForeignKey("atms_finance.ExpenseType", on_delete=models.PROTECT, related_name="expenses", null=True, blank=True)
    category = models.CharField(max_length=80)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    liters = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional fuel volume in liters for fuel expense records.",
    )
    fuel_unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional price per liter for fuel expense records.",
    )
    expense_date = models.DateField()
    proof_document = models.FileField(upload_to="finance/expenses/proofs/%Y/%m/", blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses_created",
    )

    class Meta:
        ordering = ["-expense_date", "-created_at"]
        indexes = [
            models.Index(fields=["expense_date", "category"]),
            models.Index(fields=["status", "expense_date"]),
        ]

    def __str__(self):
        return f"{self.type or self.category} - {self.amount}"

    def save(self, *args, **kwargs):
        if self.type:
            self.category = self.type.name
        if not self.expense_date:
            self.expense_date = timezone.now().date()
        super().save(*args, **kwargs)


class Revenue(TimeStampedModel):
    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.CASCADE, related_name="revenues")
    type = models.ForeignKey("atms_finance.RevenueType", on_delete=models.PROTECT, related_name="revenues")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revenues_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["trip", "type"])]

    def __str__(self):
        return f"{self.trip} - {self.type} - {self.amount}"


class DriverAllowance(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    driver = models.ForeignKey("atms_drivers.Driver", on_delete=models.CASCADE, related_name="allowances")
    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.CASCADE, related_name="allowances")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_allowances",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="allowances_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self):
        return f"{self.driver} - {self.amount} - {self.status}"


class DriverFee(TimeStampedModel):
    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"

    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.CASCADE, related_name="driver_fees")
    driver = models.ForeignKey("atms_drivers.Driver", on_delete=models.CASCADE, related_name="driver_fees")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee_date = models.DateField()
    payment_status = models.CharField(max_length=16, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-fee_date", "-created_at"]
        indexes = [models.Index(fields=["fee_date", "payment_status"])]

    def __str__(self):
        return f"{self.driver} - {self.amount}"
