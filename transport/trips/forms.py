from decimal import Decimal
import json

from django import forms
from django.db import models as db_models
from django.core.exceptions import ValidationError

from accounts.models import User
from .models import Shipment, Trip, CargoCategory, ensure_default_cargo_categories
from transport.vehicles.models import Vehicle
from transport.drivers.models import Driver
from transport.customers.models import Customer
from transport.routes.models import Route
from transport.core.models import CommodityType
from transport.orders.models import Order


INPUT_CSS = (
    "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
)


class TripForm(forms.ModelForm):
    """Form for creating and updating trips with comprehensive validation"""
    CATEGORY_COMMODITY_CODE_MAP = {
        "fuel": [CommodityType.Code.FUEL],
        "food commodity": [CommodityType.Code.GOODS],
        "general cargo": [CommodityType.Code.GOODS],
    }
    shipments = forms.ModelMultipleChoiceField(
        queryset=Shipment.objects.none(),
        required=True,
        widget=forms.SelectMultiple(attrs={'class': INPUT_CSS}),
        help_text="Select one or more prepared shipments for this trip.",
    )

    class Meta:
        model = Trip
        fields = [
            'job', 'customer', 'commodity_type', 'cargo_category', 'route', 'vehicle', 'driver',
            'quantity',
            'km_end', 'rental_fee', 'fuel_cost',
            'other_expenses', 'revenue', 'status',
        ]
        widgets = {
            'job': forms.HiddenInput(),
            'customer': forms.HiddenInput(),
            'commodity_type': forms.HiddenInput(),
            'cargo_category': forms.HiddenInput(),
            'route': forms.Select(attrs={'class': INPUT_CSS, 'required': True}),
            'vehicle': forms.Select(attrs={'class': INPUT_CSS, 'required': True}),
            'driver': forms.Select(attrs={'class': INPUT_CSS, 'required': True}),
            'quantity': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00', 'readonly': 'readonly',
                'id': 'id_quantity',
            }),
            'km_end': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'rental_fee': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'fuel_cost': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'other_expenses': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'revenue': forms.NumberInput(attrs={
                'class': INPUT_CSS, 'step': '0.01', 'min': '0', 'placeholder': '0.00',
            }),
            'status': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_default_cargo_categories()

        # Filter querysets
        self.fields['job'].queryset = Order.objects.select_related('customer', 'route').order_by('-created_at')
        self.fields['job'].required = False
        self.fields['customer'].queryset = Customer.objects.filter(status=Customer.CustomerStatus.ACTIVE)
        self.fields['customer'].required = False
        self.fields['commodity_type'].queryset = CommodityType.objects.filter(is_active=True)
        self.fields['commodity_type'].required = False
        self.fields['route'].queryset = Route.objects.filter(is_active=True)
        self.fields['cargo_category'].queryset = CargoCategory.objects.filter(is_active=True).order_by("name")
        self.fields['cargo_category'].required = False
        self.fields['status'].required = False
        self._set_commodity_queryset()

        # For vehicles/drivers: if editing, include the already-assigned resources
        if self.instance and self.instance.pk:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(
                db_models.Q(status=Vehicle.VehicleStatus.AVAILABLE) |
                db_models.Q(pk=self.instance.vehicle_id)
            )
            self.fields['driver'].queryset = Driver.objects.filter(
                db_models.Q(status=Driver.DriverStatus.AVAILABLE) |
                db_models.Q(pk=self.instance.driver_id)
            )
        else:
            self.fields['vehicle'].queryset = Vehicle.objects.filter(status=Vehicle.VehicleStatus.AVAILABLE)
            self.fields['driver'].queryset = Driver.objects.filter(status=Driver.DriverStatus.AVAILABLE)

        shipment_queryset = Shipment.objects.select_related("order", "order__unit", "customer").filter(
            status=Shipment.Status.PENDING,
            trip__isnull=True,
        )
        if self.instance and self.instance.pk:
            shipment_queryset = Shipment.objects.select_related("order", "order__unit", "customer").filter(
                db_models.Q(status=Shipment.Status.PENDING, trip__isnull=True) | db_models.Q(trip=self.instance)
            )
            self.fields["shipments"].initial = self.instance.shipments.values_list("pk", flat=True)
        self.fields["shipments"].queryset = shipment_queryset.order_by("-created_at")
        self.fields["shipments"].label_from_instance = (
            lambda shipment: (
                f"{shipment.order.order_number} | "
                f"{shipment.customer.company_name} | "
                f"{shipment.order.origin} -> {shipment.order.destination} | "
                f"{shipment.weight_kg} kg"
            )
        )

        # Help texts
        self.fields['customer'].help_text = "Auto-filled from the selected shipments"
        self.fields['job'].help_text = "Auto-linked when all selected shipments belong to the same order"
        self.fields['commodity_type'].help_text = "Auto-filled from the selected shipments"
        self.fields['cargo_category'].help_text = "Auto-filled from the selected shipments"
        self.fields['route'].help_text = "Choose the route for this trip"
        self.fields['vehicle'].help_text = "Assign a vehicle to this trip"
        self.fields['driver'].help_text = "Assign a driver to this trip"
        self.fields['shipments'].help_text = "Select one or more unassigned shipments for this trip."
        self.fields['quantity'].help_text = "Quantity is derived from the selected shipments."
        self.fields['rental_fee'].help_text = "Required only when the selected vehicle is external."
        self.fields['rental_fee'].required = False

        # Make financial fields optional for creation
        for f in ('km_end', 'fuel_cost', 'other_expenses', 'revenue', 'quantity'):
            self.fields[f].required = False
        self.fields['km_end'].widget = forms.HiddenInput()
        self.fields['fuel_cost'].widget = forms.HiddenInput()
        self.fields['other_expenses'].widget = forms.HiddenInput()
        self.fields['revenue'].widget = forms.HiddenInput()
        self.fields['status'].initial = Trip.TripStatus.PENDING_APPROVAL

        if self.instance and self.instance.pk and self.instance.shipments.exists():
            self.fields["quantity"].initial = self.instance.total_load
        vehicle_map = {
            str(vehicle.pk): vehicle.ownership_type
            for vehicle in self.fields["vehicle"].queryset
        }
        self.fields["vehicle"].widget.attrs["data-vehicle-ownership-map"] = json.dumps(vehicle_map)

    def _allowed_commodity_codes_for_category(self, cargo_category):
        if not cargo_category:
            return [value for value, _label in CommodityType.Code.choices]
        category_name = getattr(cargo_category, "name", str(cargo_category)).strip().lower()
        return self.CATEGORY_COMMODITY_CODE_MAP.get(category_name, [value for value, _label in CommodityType.Code.choices])

    def _set_commodity_queryset(self):
        cargo_category = None
        if self.is_bound:
            cargo_category_id = self.data.get("cargo_category")
            if cargo_category_id:
                cargo_category = CargoCategory.objects.filter(pk=cargo_category_id).first()
        elif self.instance and self.instance.pk:
            cargo_category = self.instance.cargo_category
        else:
            cargo_category = self.initial.get("cargo_category")

        allowed_codes = self._allowed_commodity_codes_for_category(cargo_category)
        self.fields["commodity_type"].queryset = CommodityType.objects.filter(
            is_active=True,
            code__in=allowed_codes,
        ).order_by("name")

    def clean_km_end(self):
        km_start = self.cleaned_data.get('km_start')
        km_end = self.cleaned_data.get('km_end')
        if km_start is not None and km_end is not None and km_end < km_start:
            raise ValidationError("End kilometer reading must be greater than start reading.")
        return km_end

    def clean_fuel_cost(self):
        fuel_issued = self.cleaned_data.get('fuel_issued')
        fuel_cost = self.cleaned_data.get('fuel_cost')
        if fuel_issued and fuel_cost:
            if fuel_issued > 0 and fuel_cost == 0:
                raise ValidationError("Fuel cost must be provided when fuel is issued.")
        return fuel_cost

    def clean_vehicle(self):
        vehicle = self.cleaned_data.get('vehicle')
        if not vehicle:
            return vehicle
        # On edit: allow the already-assigned vehicle
        if self.instance and self.instance.pk and self.instance.vehicle_id == vehicle.pk:
            return vehicle
        if vehicle.status != Vehicle.VehicleStatus.AVAILABLE:
            raise ValidationError(f"Vehicle {vehicle} is not available for assignment.")
        return vehicle

    def clean_driver(self):
        driver = self.cleaned_data.get('driver')
        if not driver:
            return driver
        if self.instance and self.instance.pk and self.instance.driver_id == driver.pk:
            return driver
        if driver.status != Driver.DriverStatus.AVAILABLE:
            raise ValidationError(f"Driver {driver} is not available for assignment.")
        return driver

    def clean_status(self):
        if self.instance and self.instance.pk:
            return self.instance.status
        return Trip.TripStatus.PENDING_APPROVAL

    def clean_commodity_type(self):
        commodity_type = self.cleaned_data.get("commodity_type")
        cargo_category = self.cleaned_data.get("cargo_category")
        if commodity_type and cargo_category:
            allowed_codes = self._allowed_commodity_codes_for_category(cargo_category)
            if commodity_type.code not in allowed_codes:
                raise ValidationError("Selected commodity type does not match the chosen cargo category.")
        return commodity_type

    def clean_rental_fee(self):
        rental_fee = self.cleaned_data.get("rental_fee")
        if rental_fee is None:
            return Decimal("0")
        if rental_fee < 0:
            raise ValidationError("Rental fee cannot be negative.")
        return rental_fee

    def clean_shipments(self):
        shipments = list(self.cleaned_data.get("shipments") or [])
        if not shipments:
            raise ValidationError("At least one shipment is required per trip.")

        total_weight_kg = sum((shipment.weight_kg for shipment in shipments), Decimal("0"))
        vehicle = self.cleaned_data.get("vehicle") or getattr(self.instance, "vehicle", None)
        vehicle_capacity_kg = (getattr(vehicle, "load_capacity", Decimal("0")) or Decimal("0")) * Decimal("1000")
        if vehicle and total_weight_kg > vehicle_capacity_kg:
            raise ValidationError(
                f"Total shipment weight {total_weight_kg} kg exceeds vehicle capacity {vehicle_capacity_kg} kg."
            )

        for shipment in shipments:
            if shipment.trip_id and (not self.instance.pk or shipment.trip_id != self.instance.pk):
                raise ValidationError(f"Shipment {shipment.order.order_number} is already assigned to another trip.")
            if shipment.status != Shipment.Status.PENDING and (not self.instance.pk or shipment.trip_id != self.instance.pk):
                raise ValidationError(f"Shipment {shipment.order.order_number} is not available for assignment.")
        return shipments

    def clean(self):
        cleaned_data = super().clean()
        shipments = cleaned_data.get("shipments") or []
        vehicle = cleaned_data.get("vehicle") or getattr(self.instance, "vehicle", None)
        rental_fee = cleaned_data.get("rental_fee") or Decimal("0")

        if vehicle and vehicle.ownership_type == Vehicle.OwnershipType.EXTERNAL and rental_fee <= 0:
            self.add_error("rental_fee", "Rental fee is required for external vehicles.")
        if vehicle and vehicle.ownership_type == Vehicle.OwnershipType.COMPANY:
            cleaned_data["rental_fee"] = Decimal("0")

        if not shipments:
            if not cleaned_data.get("customer"):
                cleaned_data["customer"] = getattr(self.instance, "customer", None) or self.fields["customer"].queryset.first()
            if not cleaned_data.get("commodity_type"):
                cleaned_data["commodity_type"] = getattr(self.instance, "commodity_type", None) or self.fields["commodity_type"].queryset.first()
            cleaned_data["status"] = self.instance.status if self.instance and self.instance.pk else Trip.TripStatus.PENDING_APPROVAL
            self.instance.customer = cleaned_data.get("customer")
            self.instance.commodity_type = cleaned_data.get("commodity_type")
            self.instance.status = cleaned_data["status"]
            self.instance.rental_fee = cleaned_data.get("rental_fee") or Decimal("0")
            return cleaned_data

        if shipments:
            first_shipment = shipments[0]
            first_order = first_shipment.order
            total_quantity = sum((shipment.weight_kg for shipment in shipments), Decimal("0"))
            unique_orders = {shipment.order_id for shipment in shipments}
            cleaned_data["quantity"] = total_quantity
            cleaned_data["customer"] = first_shipment.customer
            cleaned_data["job"] = first_order if len(unique_orders) == 1 else None
            cleaned_data["cargo_category"] = first_order.cargo_category
            if not cleaned_data.get("route") and first_order.route_id:
                cleaned_data["route"] = first_order.route

            selected_category = cleaned_data.get("cargo_category")
            allowed_codes = self._allowed_commodity_codes_for_category(selected_category)
            commodity_type = CommodityType.objects.filter(
                is_active=True,
                code__in=allowed_codes,
            ).order_by("name").first()
            if commodity_type is None:
                self.add_error("shipments", "Unable to derive a commodity type from the selected shipments.")
            cleaned_data["commodity_type"] = commodity_type
            cleaned_data["status"] = self.instance.status if self.instance and self.instance.pk else Trip.TripStatus.PENDING_APPROVAL

            self.instance.quantity = total_quantity
            self.instance.customer = cleaned_data["customer"]
            self.instance.job = cleaned_data["job"]
            self.instance.cargo_category = cleaned_data["cargo_category"]
            self.instance.route = cleaned_data.get("route")
            self.instance.commodity_type = cleaned_data.get("commodity_type")
            self.instance.status = cleaned_data["status"]
            self.instance.rental_fee = cleaned_data.get("rental_fee") or Decimal("0")
        return cleaned_data


class TripStatusUpdateForm(forms.ModelForm):
    """Simple form for updating just the trip status"""

    class Meta:
        model = Trip
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': INPUT_CSS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].help_text = "Update the current status of this trip"


class TripReportEmailForm(forms.Form):
    REPORT_FORMAT_PDF = "pdf"
    REPORT_FORMAT_EXCEL = "excel"
    REPORT_FORMAT_CHOICES = (
        (REPORT_FORMAT_PDF, "PDF"),
        (REPORT_FORMAT_EXCEL, "Excel"),
    )

    recipients = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        help_text="Select one or more registered users to receive the trip report.",
    )
    report_format = forms.ChoiceField(
        choices=REPORT_FORMAT_CHOICES,
        widget=forms.Select(attrs={"class": INPUT_CSS}),
        initial=REPORT_FORMAT_PDF,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipients"].queryset = User.objects.filter(
            is_active=True,
        ).exclude(email="").order_by("full_name", "email")
        self.fields["recipients"].label_from_instance = (
            lambda user: f"{user.full_name} ({user.email})"
        )

    def clean_recipients(self):
        recipients = list(self.cleaned_data.get("recipients") or [])
        if not recipients:
            raise ValidationError("Select at least one user to receive the report.")
        missing_email = [user.full_name for user in recipients if not user.email]
        if missing_email:
            raise ValidationError("All selected users must have email addresses.")
        return recipients

class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = ["order", "weight_kg", "carriage_type", "container_number"]
        widgets = {
            "order": forms.Select(attrs={"class": INPUT_CSS}),
            "weight_kg": forms.NumberInput(
                attrs={"class": INPUT_CSS, "step": "0.01", "min": "0.01", "placeholder": "0.00"}
            ),
            "carriage_type": forms.Select(attrs={"class": INPUT_CSS}),
            "container_number": forms.TextInput(
                attrs={"class": INPUT_CSS, "placeholder": "Container number"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        order_queryset = Shipment.available_orders_queryset()
        if self.instance and self.instance.pk and self.instance.order_id:
            order_queryset = (
                Order.objects.select_related("customer", "route", "cargo_category", "unit")
                .filter(db_models.Q(pk=self.instance.order_id) | db_models.Q(pk__in=order_queryset.values("pk")))
                .order_by("-created_at")
            )
        self.fields["order"].queryset = order_queryset
        self.fields["order"].label_from_instance = self._order_label
        self.fields["order"].help_text = "Select the order/job to prepare a shipment for."
        self.fields["weight_kg"].label = "Weight"
        self.fields["weight_kg"].help_text = "The field fetches the order remaining weight in kg and still allows manual editing."
        self.fields["carriage_type"].help_text = "Select how this cargo will be carried."
        self.fields["container_number"].help_text = "Required only for container shipments."
        self.fields["container_number"].required = False

    def _order_label(self, order):
        cargo_category = getattr(order.cargo_category, "name", "Uncategorised")
        origin = getattr(order.route, "origin", "")
        destination = getattr(order.route, "destination", "")
        route_label = f"{origin} -> {destination}" if origin or destination else "Route not set"
        return (
            f"{order.order_number} | {order.customer.company_name} | "
            f"{cargo_category} | {route_label} | Remaining {order.formatted_remaining_weight_kg}"
        )

    def clean(self):
        cleaned_data = super().clean()
        order = cleaned_data.get("order")
        weight_kg = cleaned_data.get("weight_kg")
        carriage_type = cleaned_data.get("carriage_type")
        container_number = (cleaned_data.get("container_number") or "").strip()
        if order and weight_kg is not None:
            if weight_kg <= Decimal("0"):
                self.add_error("weight_kg", "Shipment weight must be greater than zero.")
            elif weight_kg > (order.remaining_weight_kg + (self.instance.weight_kg or Decimal("0")) if self.instance and self.instance.pk and self.instance.order_id == order.pk else order.remaining_weight_kg):
                self.add_error(
                    "weight_kg",
                    f"Shipment weight cannot exceed the order remaining weight of {order.formatted_remaining_weight_kg}.",
                )
            elif order.weight_kg_value <= 0 or order.total_quantity_value <= 0:
                self.add_error("order", "Selected order must have both total quantity and weight configured.")

        if carriage_type == Shipment.CarriageType.CONTAINER and not container_number:
            self.add_error("container_number", "Container number is required for container shipments.")
        if carriage_type != Shipment.CarriageType.CONTAINER:
            cleaned_data["container_number"] = ""
        return cleaned_data

    def save(self, commit=True):
        shipment = super().save(commit=False)
        if shipment.order_id:
            shipment.customer = shipment.order.customer
            if not shipment.pk:
                shipment.status = Shipment.Status.PENDING
                shipment.trip = None
        if commit:
            shipment.save()
        return shipment
