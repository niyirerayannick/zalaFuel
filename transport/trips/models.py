from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, FloatField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from transport.core.models import TimeStampedModel
from transport.orders.models import Order


class CargoCategory(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name", "is_active"])]

    def __str__(self):
        return self.name


def ensure_default_cargo_categories():
    defaults = ["Fuel", "Food Commodity", "General Cargo"]
    existing_count = CargoCategory.objects.count()
    if existing_count:
        return
    for name in defaults:
        CargoCategory.objects.get_or_create(name=name, defaults={"is_active": True})


class Trip(TimeStampedModel):
    class TripStatus(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        DELIVERED = "DELIVERED", "Delivered"
        COMPLETED = "COMPLETED", "Completed"
        CLOSED = "CLOSED", "Closed"

    class DriverResponse(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
    
    # Backward compatibility property
    STATUS_CHOICES = TripStatus.choices
    WORKFLOW_TRANSITIONS = {
        TripStatus.DRAFT: {TripStatus.PENDING_APPROVAL},
        TripStatus.PENDING_APPROVAL: {TripStatus.APPROVED, TripStatus.REJECTED},
        TripStatus.REJECTED: set(),
        TripStatus.APPROVED: {TripStatus.IN_TRANSIT, TripStatus.ASSIGNED},
        TripStatus.ASSIGNED: {TripStatus.IN_TRANSIT},
        TripStatus.IN_TRANSIT: {TripStatus.COMPLETED, TripStatus.DELIVERED},
        TripStatus.DELIVERED: {TripStatus.COMPLETED},
        TripStatus.COMPLETED: {TripStatus.CLOSED},
        TripStatus.CLOSED: set(),
    }

    order_number = models.CharField(max_length=40, unique=True, blank=True)
    job = models.ForeignKey("atms_orders.Order", on_delete=models.SET_NULL, null=True, blank=True, related_name="trip_records")
    customer = models.ForeignKey("atms_customers.Customer", on_delete=models.PROTECT, related_name="trips")
    commodity_type = models.ForeignKey("atms_core.CommodityType", on_delete=models.PROTECT, related_name="trips")
    cargo_category = models.ForeignKey("atms_trips.CargoCategory", on_delete=models.SET_NULL, null=True, blank=True, related_name="trips")
    route = models.ForeignKey("atms_routes.Route", on_delete=models.PROTECT, related_name="trips")
    vehicle = models.ForeignKey("atms_vehicles.Vehicle", on_delete=models.PROTECT, related_name="trips")
    driver = models.ForeignKey("atms_drivers.Driver", on_delete=models.PROTECT, related_name="trips")

    quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text="Quantity of commodity (liters for Fuel, kg for Goods)",
    )
    quantity_unit = models.CharField(
        max_length=16, blank=True, default="",
        help_text="Auto-set: liters for Fuel, kg for Goods",
    )

    km_start = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    km_end = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    fuel_issued = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    rental_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    fuel_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    other_expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    distance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_per_km = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    revenue_per_km = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=TripStatus.choices, default=TripStatus.PENDING_APPROVAL)
    driver_response = models.CharField(
        max_length=16,
        choices=DriverResponse.choices,
        default=DriverResponse.PENDING,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["order_number"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["customer", "route"]),
            models.Index(fields=["vehicle", "driver"]),
            models.Index(fields=["job", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle"],
                condition=Q(status__in=["ASSIGNED", "IN_TRANSIT"]),
                name="atms_unique_active_vehicle_trip",
            ),
            models.UniqueConstraint(
                fields=["driver"],
                condition=Q(status__in=["ASSIGNED", "IN_TRANSIT"]),
                name="atms_unique_active_driver_trip",
            ),
        ]
        permissions = [
            ("approve_trip", "Can approve trip"),
            ("close_trip", "Can close trip"),
        ]

    def __str__(self):
        return self.order_number or f"Trip {self.pk}"

    def clean(self):
        if self.km_end and self.km_end < self.km_start:
            raise ValidationError({"km_end": "km_end cannot be less than km_start."})

        if self.pk:
            previous_status = (
                Trip.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            )
            if previous_status and previous_status != self.status:
                self.validate_status_transition(previous_status, self.status)

        can_vehicle_assign, vehicle_reason = self.vehicle.can_be_assigned()
        can_driver_assign, driver_reason = self.driver.can_be_assigned()

        if self.status in {self.TripStatus.ASSIGNED, self.TripStatus.IN_TRANSIT}:
            if not can_vehicle_assign and self.vehicle.status != self.vehicle.VehicleStatus.ASSIGNED:
                raise ValidationError({"vehicle": vehicle_reason})
            if not can_driver_assign and self.driver.status != self.driver.DriverStatus.ASSIGNED:
                raise ValidationError({"driver": driver_reason})
        if self.vehicle_id and self.vehicle.ownership_type == self.vehicle.OwnershipType.EXTERNAL and (self.rental_fee or Decimal("0")) <= 0:
            raise ValidationError({"rental_fee": "Rental fee is required for trips using external vehicles."})
        if self.vehicle_id and self.vehicle.ownership_type == self.vehicle.OwnershipType.COMPANY and (self.rental_fee or Decimal("0")) > 0:
            self.rental_fee = Decimal("0")
        if self.vehicle_id and self.total_load_weight_kg > ((self.vehicle.load_capacity or Decimal("0")) * Decimal("1000")):
            raise ValidationError({"vehicle": "Trip load exceeds the vehicle load capacity."})

    def calculate_distance(self):
        if self.km_end <= self.km_start:
            return Decimal("0")
        return self.km_end - self.km_start

    @classmethod
    def allowed_status_transitions(cls, from_status):
        return cls.WORKFLOW_TRANSITIONS.get(from_status, set())

    @classmethod
    def validate_status_transition(cls, from_status, to_status):
        if from_status == to_status:
            return
        allowed_statuses = cls.allowed_status_transitions(from_status)
        if to_status not in allowed_statuses:
            allowed_labels = ", ".join(
                cls.TripStatus(status).label for status in sorted(allowed_statuses)
            ) or "no further transitions"
            raise ValidationError(
                {
                    "status": (
                        f"Invalid trip status transition from "
                        f"{cls.TripStatus(from_status).label} to {cls.TripStatus(to_status).label}. "
                        f"Allowed next status: {allowed_labels}."
                    )
                }
            )

    def can_transition_to(self, to_status):
        try:
            self.validate_status_transition(self.status, to_status)
        except ValidationError:
            return False
        return True

    def recalculate_financials(self):
        self.distance = self.calculate_distance()
        self.revenue = self.total_revenue
        self.total_cost = self.total_expenses
        self.profit = self.net_profit
        if self.distance > 0:
            self.cost_per_km = self.total_cost / self.distance
            self.revenue_per_km = (self.revenue or Decimal("0")) / self.distance
        else:
            self.cost_per_km = Decimal("0")
            self.revenue_per_km = Decimal("0")

    def save(self, *args, **kwargs):
        if not self.order_number:
            date_prefix = timezone.now().strftime("%Y%m%d")
            seed = Trip.objects.filter(order_number__startswith=f"ZALA Terminal-{date_prefix}").count() + 1
            self.order_number = f"ZALA Terminal-{date_prefix}-{seed:04d}"
        if self.status in {self.TripStatus.DRAFT, self.TripStatus.PENDING_APPROVAL, self.TripStatus.APPROVED}:
            self.driver_response = self.DriverResponse.PENDING
        if self.vehicle_id and self.vehicle.ownership_type == self.vehicle.OwnershipType.COMPANY:
            self.rental_fee = Decimal("0")
        # Auto-set quantity_unit from commodity_type
        if self.commodity_type_id:
            try:
                code = self.commodity_type.code
            except Exception:
                code = ""
            self.quantity_unit = "liters" if code == "FUEL" else "kg"
        self.recalculate_financials()
        super().save(*args, **kwargs)

    @property
    def total_expenses(self):
        if not self.pk:
            expense_total = self.other_expenses or Decimal("0")
            return expense_total + (self.fuel_cost or Decimal("0"))
        expense_total = self.expenses.aggregate(total=Sum("amount")).get("total") or Decimal("0")
        return expense_total + (self.fuel_cost or Decimal("0"))

    @property
    def gross_profit(self):
        if self.job_id and self.job and self.job.quoted_price:
            return self.job.quoted_price
        return self.expected_revenue

    @property
    def total_revenue(self):
        if not self.pk:
            return self.revenue or Decimal("0")
        revenue_total = self.revenues.aggregate(total=Sum("amount")).get("total")
        if revenue_total is not None:
            return revenue_total
        payment_total = self.payments.exclude(status="FAILED").aggregate(total=Sum("amount")).get("total")
        if payment_total is not None:
            return payment_total
        return self.revenue or Decimal("0")

    @property
    def net_profit(self):
        return (self.gross_profit or Decimal("0")) - self.total_expenses

    @property
    def total_load(self):
        if not self.pk:
            return self.quantity or Decimal("0")
        shipment_total = self.shipments.aggregate(total=Sum("weight_kg")).get("total")
        if shipment_total is not None:
            return shipment_total
        return self.quantity or Decimal("0")

    @property
    def total_load_weight_kg(self):
        if not self.pk:
            if self.job_id and self.job:
                return self.job.weight_kg_value
            return Decimal("0")
        return sum((shipment.weight_kg for shipment in self.shipments.select_related("order")), Decimal("0"))

    @property
    def is_groupage(self):
        if not self.pk:
            return False
        return self.shipments.count() > 1

    @property
    def related_orders(self):
        if self.job_id:
            return Order.objects.filter(pk=self.job_id)
        if not self.pk:
            return Order.objects.none()
        return Order.objects.filter(shipments__trip=self).distinct()

    @property
    def expected_revenue(self):
        if self.job_id and self.job and self.job.quoted_price:
            return self.job.quoted_price
        if not self.pk:
            return self.revenue or Decimal("0")

        totals = {}
        for shipment in self.shipments.select_related("order"):
            order = shipment.order
            order_total_quantity = order.total_quantity_value
            if order_total_quantity <= 0 or not order.quoted_price:
                continue
            allocated = (order.quoted_price * shipment.quantity) / order_total_quantity
            totals[order.pk] = totals.get(order.pk, Decimal("0")) + allocated
        if totals:
            return sum(totals.values(), Decimal("0"))
        return self.revenue or Decimal("0")


class Shipment(TimeStampedModel):
    class CarriageType(models.TextChoices):
        CONTAINER = "container", "Container"
        BULK = "bulk", "Bulk"
        LOOSE = "loose", "Loose"
        TANKER = "tanker", "Tanker"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_TRANSIT = "IN_TRANSIT", "In Transit"
        DELIVERED = "DELIVERED", "Delivered"

    trip = models.ForeignKey("atms_trips.Trip", on_delete=models.CASCADE, related_name="shipments", null=True, blank=True)
    order = models.ForeignKey("atms_orders.Order", on_delete=models.CASCADE, related_name="shipments")
    customer = models.ForeignKey("atms_customers.Customer", on_delete=models.CASCADE, related_name="shipments")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    weight_kg = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    carriage_type = models.CharField(
        max_length=20,
        choices=CarriageType.choices,
        default=CarriageType.OTHER,
    )
    container_number = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    sender_name = models.CharField(max_length=120, default="ZALA Terminal")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["trip", "customer"]),
            models.Index(fields=["order", "trip"]),
            models.Index(fields=["status", "created_at"]),
        ]
    def __str__(self):
        return f"{self.trip} - {self.customer} - {self.quantity}"

    @property
    def external_sender_name(self):
        return "ZALA Terminal"

    def calculate_quantity_from_weight(self):
        if not self.order_id:
            return Decimal("0")
        order_total_weight = self.order.weight_kg_value
        order_total_quantity = self.order.total_quantity_value
        if order_total_weight <= 0 or order_total_quantity <= 0 or self.weight_kg is None:
            return Decimal("0")
        calculated = (Decimal(str(self.weight_kg or 0)) * order_total_quantity) / order_total_weight
        return calculated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def calculate_weight_kg(self):
        if not self.order_id:
            return Decimal("0")
        order_total_quantity = self.order.total_quantity_value
        if order_total_quantity <= 0 or self.order.weight_kg_value <= 0 or self.quantity is None:
            return Decimal("0")
        calculated = (self.order.weight_kg_value * self.quantity) / order_total_quantity
        return calculated.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def available_orders_queryset(cls):
        return (
            Order.objects.select_related("customer", "route", "cargo_category", "unit")
            .annotate(
                shipped_weight_kg=Coalesce(
                    Sum("shipments__weight_kg"),
                    Value(0.0),
                    output_field=FloatField(),
                )
            )
            .annotate(
                remaining_weight_db=F("weight_kg") - F("shipped_weight_kg")
            )
            .filter(weight_kg__gt=0, remaining_weight_db__gt=0)
            .order_by("-created_at")
        )

    def clean(self):
        errors = {}
        if self.weight_kg is not None and self.weight_kg > 0:
            self.quantity = self.calculate_quantity_from_weight()
        else:
            self.weight_kg = self.calculate_weight_kg()

        if self.weight_kg is None or self.weight_kg <= 0:
            errors["weight_kg"] = "Shipment weight must be greater than zero."

        if self.quantity is None or self.quantity <= 0:
            errors["weight_kg"] = "Shipment weight must map to a valid shipped quantity."

        if self.order_id and self.customer_id and getattr(self.order, "customer_id", None) != self.customer_id:
            errors["customer"] = "Shipment customer must match the selected order customer."

        if self.carriage_type == self.CarriageType.CONTAINER and not (self.container_number or "").strip():
            errors["container_number"] = "Container number is required when carriage type is container."

        if self.carriage_type != self.CarriageType.CONTAINER:
            self.container_number = ""

        if self.order_id and self.weight_kg is not None:
            existing_for_order = (
                Shipment.objects.exclude(pk=self.pk)
                .filter(order_id=self.order_id)
                .aggregate(total=Sum("weight_kg"))
                .get("total")
                or Decimal("0")
            )
            projected_order_total = existing_for_order + self.weight_kg
            if projected_order_total > self.order.weight_kg_value:
                errors["weight_kg"] = (
                    f"Shipment weight exceeds the order remaining weight. "
                    f"Remaining weight is {self.order.formatted_remaining_weight_kg}."
                )

        if self.trip_id and self.weight_kg is not None:
            existing_weight = sum(
                (shipment.weight_kg for shipment in self.trip.shipments.select_related("order").exclude(pk=self.pk)),
                Decimal("0"),
            )
            projected_weight = existing_weight + self.weight_kg
            vehicle_capacity = getattr(self.trip.vehicle, "load_capacity", None)
            vehicle_capacity_kg = (vehicle_capacity or Decimal("0")) * Decimal("1000")
            if vehicle_capacity is not None and projected_weight > vehicle_capacity_kg:
                errors["weight_kg"] = (
                    f"Adding this shipment would overload the vehicle. "
                        f"Projected weight {projected_weight} kg exceeds capacity {vehicle_capacity_kg} kg."
                )

        if self.trip_id and self.status == self.Status.PENDING:
            self.status = self.Status.ASSIGNED

        if not self.trip_id and self.status != self.Status.PENDING:
            errors["status"] = "Unassigned shipments must remain in pending status."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.order_id:
            self.customer = self.order.customer
        if self.weight_kg is not None and self.weight_kg > 0:
            self.quantity = self.calculate_quantity_from_weight()
        else:
            self.weight_kg = self.calculate_weight_kg()
        self.sender_name = "ZALA Terminal"
        self.full_clean()
        return super().save(*args, **kwargs)
