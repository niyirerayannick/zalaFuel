import uuid
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import Sum

from accounts.currency import CURRENCY_SYMBOLS


def _quantity_decimal(value):
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal("0")


def _format_quantity_value(value):
    normalized = _quantity_decimal(value)
    formatted = format(normalized, "f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted or "0"


class Unit(models.Model):
    class MeasurementCategory(models.TextChoices):
        COUNT = "count", "Count"
        WEIGHT = "weight", "Weight"
        VOLUME = "volume", "Volume"

    name = models.CharField(max_length=100, unique=True)
    symbol = models.CharField(max_length=20, unique=True)
    measurement_category = models.CharField(
        max_length=20,
        choices=MeasurementCategory.choices,
        default=MeasurementCategory.COUNT,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class Order(models.Model):
    """Orders represent customer requests before trips are created"""
    
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved" 
        REJECTED = "rejected", "Rejected"
        ASSIGNED = "assigned", "Assigned to Trip"
        IN_TRANSIT = "in_transit", "In Transit"
        DELIVERED = "delivered", "Delivered"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
    
    class CommodityType(models.TextChoices):
        DIESEL = "diesel", "Diesel"
        PETROL = "petrol", "Petrol"
        JET_A1 = "jet_a1", "Jet A1"
        BITUMEN = "bitumen", "Bitumen"
        GENERAL_CARGO = "general_cargo", "General Cargo"
        ELECTRONICS = "electronics", "Electronics"
        TEXTILES = "textiles", "Textiles"
        FOOD_BEVERAGE = "food_beverage", "Food & Beverage"
        MACHINERY = "machinery", "Machinery"
        CHEMICALS = "chemicals", "Chemicals"
        CONSTRUCTION = "construction", "Construction Materials"
        AUTOMOTIVE = "automotive", "Automotive Parts"
        PHARMACEUTICALS = "pharmaceuticals", "Pharmaceuticals"
        FURNITURE = "furniture", "Furniture"
        OTHER = "other", "Other"

    class PaymentTerms(models.TextChoices):
        DAYS_7 = "7_days", "7 days"
        DAYS_15 = "15_days", "15 days"
        DAYS_30 = "30_days", "30 days"
        DAYS_45 = "45_days", "45 days"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey('atms_customers.Customer', on_delete=models.CASCADE, related_name='orders')
    cargo_category = models.ForeignKey(
        "atms_trips.CargoCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    
    # Order Details
    commodity_type = models.CharField(max_length=30, choices=CommodityType.choices)
    commodity_description = models.TextField()
    quantity = models.CharField(max_length=100)  # e.g., "50 tons", "100 boxes", etc.
    total_quantity = models.FloatField()
    unit = models.ForeignKey(
        "atms_orders.Unit",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )
    weight_kg = models.FloatField(
        null=True,
        blank=True,
        help_text="Total cargo weight in kilograms.",
    )
    
    # Route Information
    route = models.ForeignKey('atms_routes.Route', on_delete=models.CASCADE, related_name='orders')
    pickup_address = models.TextField()
    delivery_address = models.TextField()
    pickup_contact = models.CharField(max_length=200, blank=True)
    delivery_contact = models.CharField(max_length=200, blank=True)
    
    # Dates
    requested_pickup_date = models.DateTimeField()
    requested_delivery_date = models.DateTimeField()
    estimated_departure = models.DateTimeField(null=True, blank=True)
    
    # Financial Information
    quoted_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_terms = models.CharField(max_length=20, choices=PaymentTerms.choices, default=PaymentTerms.DAYS_30)
    profit_estimate = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Special Requirements
    special_instructions = models.TextField(blank=True)
    requires_insurance = models.BooleanField(default=False)
    requires_special_handling = models.BooleanField(default=False)
    fragile_items = models.BooleanField(default=False)
    
    # Status and Tracking
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    priority_level = models.CharField(max_length=10, choices=[
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='normal')
    
    # Approval Information
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_orders')
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Assignment Information
    assigned_trip = models.ForeignKey(
        'atms_trips.Trip',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_orders',
        help_text="Legacy/current trip pointer. Historical trip linkage is stored in Trip.job and trip shipments.",
    )
    assigned_vehicle = models.ForeignKey('atms_vehicles.Vehicle', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders')
    assigned_driver = models.ForeignKey('atms_drivers.Driver', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders')
    
    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_orders')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_orders')
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order {self.order_number} - {self.customer.company_name if self.customer else 'No Customer'}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()

        self.quantity = self.build_quantity_display()
        self.profit_estimate = None
            
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number"""
        import datetime
        now = datetime.datetime.now()
        prefix = "ORD"
        date_part = now.strftime("%Y%m%d")
        
        # Find the last order for today
        today_orders = Order.objects.filter(
            order_number__startswith=f"{prefix}{date_part}"
        ).count()
        
        sequence = str(today_orders + 1).zfill(3)
        return f"{prefix}{date_part}{sequence}"
    
    def can_be_assigned(self):
        """Check if order can be assigned to a trip"""
        return self.status == self.Status.APPROVED
    
    def can_be_approved(self):
        """Check if order can be approved"""
        return self.status == self.Status.PENDING_APPROVAL
    
    def get_profit_margin(self):
        """Calculate profit margin percentage"""
        if self.quoted_price and self.profit_estimate:
            return (float(self.profit_estimate) / float(self.quoted_price)) * 100
        return 0

    def build_quantity_display(self):
        total_quantity = self.total_quantity_value
        if total_quantity <= 0 or not self.unit_id:
            return ""
        if self.unit_id:
            return f"{_format_quantity_value(total_quantity)} {self.unit.symbol}"
        return _format_quantity_value(total_quantity)

    @property
    def display_quantity(self):
        return self.formatted_weight_kg or self.build_quantity_display()

    @property
    def formatted_total_quantity(self):
        return _format_quantity_value(self.total_quantity_value)

    @property
    def total_quantity_value(self):
        return _quantity_decimal(self.total_quantity)

    @property
    def weight_kg_value(self):
        return _quantity_decimal(self.weight_kg)

    @property
    def quantity_unit_symbol(self):
        return getattr(self.unit, "symbol", "")

    @property
    def formatted_weight_kg(self):
        if self.weight_kg_value <= 0:
            return ""
        return f"{_format_quantity_value(self.weight_kg_value)} kg"

    @property
    def currency_code(self):
        from accounts.models import SystemSettings

        settings_obj = SystemSettings.get_settings()
        if settings_obj and settings_obj.currency:
            return settings_obj.currency
        return getattr(settings, "DEFAULT_CURRENCY", "USD")

    @property
    def currency_symbol(self):
        from accounts.models import SystemSettings

        settings_obj = SystemSettings.get_settings()
        if settings_obj and settings_obj.currency_symbol:
            return settings_obj.currency_symbol
        return CURRENCY_SYMBOLS.get(self.currency_code, self.currency_code)

    @property
    def total_payments(self):
        total = Decimal("0")
        for payment in self.payments.filter(status__in=["PARTIAL", "PAID"]):
            if payment.status == "PAID":
                total += payment.amount or Decimal("0")
            else:
                total += payment.amount_paid or Decimal("0")
        return total

    @property
    def total_invoiced(self):
        return (
            self.payments.exclude(status="FAILED").aggregate(total=Sum("amount")).get("total")
            or Decimal("0")
        )

    @property
    def outstanding_balance(self):
        return (self.quoted_price or Decimal("0")) - self.total_payments

    @property
    def origin(self):
        return getattr(self.route, "origin", "")

    @property
    def destination(self):
        return getattr(self.route, "destination", "")

    @property
    def allocated_quantity(self):
        return self.shipments.aggregate(total=Sum("quantity")).get("total") or Decimal("0")

    @property
    def remaining_quantity(self):
        remaining = self.total_quantity_value - self.allocated_quantity
        return remaining if remaining > 0 else Decimal("0")

    @property
    def allocated_weight_kg(self):
        return sum((shipment.weight_kg for shipment in self.shipments.select_related("order")), Decimal("0"))

    @property
    def remaining_weight_kg(self):
        remaining = self.weight_kg_value - self.allocated_weight_kg
        return remaining if remaining > 0 else Decimal("0")

    @property
    def formatted_remaining_weight_kg(self):
        if self.remaining_weight_kg <= 0:
            return "0 kg"
        return f"{_format_quantity_value(self.remaining_weight_kg)} kg"


class OrderStatusHistory(models.Model):
    """Track order status changes and history"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, choices=Order.Status.choices, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=Order.Status.choices)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    change_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.previous_status} → {self.new_status}"


class OrderDocument(models.Model):
    """Documents attached to orders"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=255)
    document_type = models.CharField(max_length=50, choices=[
        ('quote', 'Quotation'),
        ('contract', 'Contract'),
        ('invoice', 'Invoice'),
        ('receipt', 'Receipt'),
        ('insurance', 'Insurance Document'),
        ('permit', 'Transport Permit'),
        ('other', 'Other')
    ])
    file = models.FileField(upload_to='orders/documents/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"{self.order.order_number} - {self.name}"


class OrderNote(models.Model):
    """Internal notes and communications for orders"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notes')
    note = models.TextField()
    is_internal = models.BooleanField(default=True, help_text="Internal notes are not visible to customers")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        creator = self.created_by.full_name if self.created_by else 'Unknown'
        return f"Note for {self.order.order_number} by {creator}"
