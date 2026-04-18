from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from transport.analytics.services import invalidate_dashboard_cache
from transport.finance.models import DriverAllowance, Revenue, RevenueType
from transport.finance.services import generate_invoices_for_trip
from transport.finance.services import sync_trip_rental_expense
from transport.messaging.services import (
    notify_customer_delivery_confirmed,
    notify_customer_trip_in_transit,
    notify_trip_invoice_ready,
)

from .models import Shipment, Trip


class TripWorkflowError(ValidationError):
    pass


class TripWorkflowService:
    @staticmethod
    def _orders_on_trip(trip):
        if trip.job_id and trip.job:
            return [trip.job]
        if not trip.pk:
            return []
        seen = {}
        for shipment in trip.shipments.select_related("order"):
            seen[shipment.order_id] = shipment.order
        return list(seen.values())

    @staticmethod
    def _sync_order_assignments(*, trip, default_status=None):
        orders_on_trip = TripWorkflowService._orders_on_trip(trip)

        for order in orders_on_trip:
            order.assigned_trip = trip
            order.assigned_vehicle = trip.vehicle
            order.assigned_driver = trip.driver
            if default_status:
                order.status = default_status
            order.save(update_fields=["assigned_trip", "assigned_vehicle", "assigned_driver", "status", "updated_at"])

    @staticmethod
    def sync_trip_shipments(*, trip, shipments):
        shipments = list(shipments)
        if not shipments:
            raise TripWorkflowError({"shipments": ["At least one shipment is required for a trip."]})

        total_quantity = sum((shipment.weight_kg for shipment in shipments), Decimal("0"))
        total_weight_kg = sum((shipment.weight_kg for shipment in shipments), Decimal("0"))
        vehicle_capacity = getattr(trip.vehicle, "load_capacity", None) or Decimal("0")
        vehicle_capacity_kg = vehicle_capacity * Decimal("1000")
        if vehicle_capacity and total_weight_kg > vehicle_capacity_kg:
            raise TripWorkflowError(
                {
                    "shipments": [
                        f"Total shipment weight {total_weight_kg} kg exceeds vehicle capacity {vehicle_capacity_kg} kg."
                    ]
                }
            )

        current_shipments = list(trip.shipments.all()) if trip.pk else []
        selected_ids = {shipment.pk for shipment in shipments}
        released_shipments = [shipment for shipment in current_shipments if shipment.pk not in selected_ids]
        for shipment in released_shipments:
            shipment.trip = None
            shipment.status = Shipment.Status.PENDING
            shipment.save(update_fields=["trip", "status", "sender_name", "updated_at"])

        for shipment in shipments:
            if shipment.trip_id and shipment.trip_id != trip.pk:
                raise TripWorkflowError({"shipments": [f"Shipment {shipment.pk} is already assigned to another trip."]})
            shipment.trip = trip
            shipment.status = Shipment.Status.ASSIGNED
            shipment.save(update_fields=["trip", "status", "sender_name", "updated_at"])

        trip.quantity = total_quantity
        if shipments:
            trip.customer = shipments[0].customer
            unique_orders = {shipment.order_id for shipment in shipments}
            trip.job_id = shipments[0].order_id if len(unique_orders) == 1 else None
        trip.save(update_fields=["quantity", "customer", "job", "updated_at"])
        TripWorkflowService._sync_order_assignments(trip=trip, default_status=trip.job.Status.ASSIGNED if shipments else None)

        for order in {shipment.order for shipment in released_shipments}:
            if not order.shipments.filter(trip__isnull=False).exists():
                order.assigned_trip = None
                order.assigned_vehicle = None
                order.assigned_driver = None
                if order.status == order.Status.ASSIGNED:
                    order.status = order.Status.APPROVED
                order.save(update_fields=["assigned_trip", "assigned_vehicle", "assigned_driver", "status", "updated_at"])

        return trip

    @staticmethod
    def transition_trip(*, trip, to_status, approved_by=None):
        try:
            trip.validate_status_transition(trip.status, to_status)
        except ValidationError as exc:
            raise TripWorkflowError(exc.message_dict) from exc

        if to_status == Trip.TripStatus.APPROVED:
            return TripWorkflowService.approve_trip(trip=trip, approved_by=approved_by)
        if to_status == Trip.TripStatus.IN_TRANSIT:
            return TripWorkflowService.start_trip(trip=trip)
        if to_status == Trip.TripStatus.COMPLETED:
            return TripWorkflowService.complete_trip(trip=trip)

        trip.status = to_status
        trip.save(update_fields=["status", "updated_at"])
        return trip

    @staticmethod
    @transaction.atomic
    def create_trip(
        *,
        job,
        customer,
        commodity_type,
        route,
        vehicle,
        driver,
        quantity=Decimal("0"),
        cargo_category=None,
        rental_fee=Decimal("0"),
        created_by=None,
    ):
        trip = Trip.objects.create(
            job=job,
            customer=customer,
            commodity_type=commodity_type,
            cargo_category=cargo_category,
            route=route,
            vehicle=vehicle,
            driver=driver,
            quantity=quantity,
            rental_fee=rental_fee,
            status=Trip.TripStatus.PENDING_APPROVAL,
        )
        sync_trip_rental_expense(trip=trip, created_by=created_by)
        driver.assigned_vehicle = vehicle
        driver.save(update_fields=["assigned_vehicle", "updated_at"])
        if job:
            job.assigned_vehicle = vehicle
            job.assigned_driver = driver
            job.assigned_trip = trip
            job.status = job.Status.ASSIGNED
            job.save(update_fields=["assigned_trip", "assigned_vehicle", "assigned_driver", "status", "updated_at"])
        invalidate_dashboard_cache()
        return trip

    @staticmethod
    @transaction.atomic
    def approve_trip(*, trip, approved_by):
        trip.validate_status_transition(trip.status, Trip.TripStatus.APPROVED)
        trip.status = Trip.TripStatus.APPROVED
        trip.save(update_fields=["status", "updated_at"])
        for order in TripWorkflowService._orders_on_trip(trip):
            order.status = order.Status.APPROVED
            order.approved_by = approved_by
            order.save(update_fields=["status", "approved_by", "updated_at"])
        invoices = generate_invoices_for_trip(trip)
        if invoices:
            notify_trip_invoice_ready(trip, invoices[0])
        invalidate_dashboard_cache()
        return trip

    @staticmethod
    @transaction.atomic
    def reject_trip(*, trip):
        trip.validate_status_transition(trip.status, Trip.TripStatus.REJECTED)
        trip.status = Trip.TripStatus.REJECTED
        trip.save(update_fields=["status", "updated_at"])

        trip.expenses.all().delete()
        DriverAllowance.objects.filter(trip=trip).delete()

        for shipment in trip.shipments.all():
            shipment.trip = None
            shipment.status = Shipment.Status.PENDING
            shipment.save(update_fields=["trip", "status", "sender_name", "updated_at"])

        if trip.driver:
            trip.driver.status = trip.driver.DriverStatus.AVAILABLE
            trip.driver.availability_status = trip.driver.AvailabilityStatus.AVAILABLE
            trip.driver.assigned_vehicle = None
            trip.driver.save(update_fields=["status", "availability_status", "assigned_vehicle", "updated_at"])

        for order in TripWorkflowService._orders_on_trip(trip):
            order.assigned_trip = None
            order.assigned_vehicle = None
            order.assigned_driver = None
            if order.status == order.Status.ASSIGNED:
                order.status = order.Status.APPROVED
            order.save(update_fields=["assigned_trip", "assigned_vehicle", "assigned_driver", "status", "updated_at"])
        invalidate_dashboard_cache()
        return trip

    @staticmethod
    @transaction.atomic
    def start_trip(*, trip):
        trip.validate_status_transition(trip.status, Trip.TripStatus.IN_TRANSIT)
        trip.status = Trip.TripStatus.IN_TRANSIT
        trip.save(update_fields=["status", "updated_at"])
        trip.shipments.update(status=Shipment.Status.IN_TRANSIT, sender_name="ZALA Terminal")
        if trip.driver:
            trip.driver.status = trip.driver.DriverStatus.ASSIGNED
            trip.driver.availability_status = trip.driver.AvailabilityStatus.IN_TRANSIT
            trip.driver.assigned_vehicle = trip.vehicle
            trip.driver.save(update_fields=["status", "availability_status", "assigned_vehicle", "updated_at"])
        for order in TripWorkflowService._orders_on_trip(trip):
            order.status = order.Status.IN_TRANSIT
            order.assigned_trip = trip
            order.assigned_vehicle = trip.vehicle
            order.assigned_driver = trip.driver
            order.save(update_fields=["status", "assigned_trip", "assigned_vehicle", "assigned_driver", "updated_at"])
        notify_customer_trip_in_transit(trip)
        invalidate_dashboard_cache()
        return trip

    @staticmethod
    @transaction.atomic
    def complete_trip(*, trip):
        trip.validate_status_transition(trip.status, Trip.TripStatus.COMPLETED)
        trip.status = Trip.TripStatus.COMPLETED
        trip.save(update_fields=["status", "updated_at"])
        trip.shipments.update(status=Shipment.Status.DELIVERED, sender_name="ZALA Terminal")
        if trip.vehicle:
            trip.vehicle.status = trip.vehicle.VehicleStatus.AVAILABLE
            trip.vehicle.save(update_fields=["status", "updated_at"])
        if trip.driver:
            trip.driver.status = trip.driver.DriverStatus.AVAILABLE
            trip.driver.availability_status = trip.driver.AvailabilityStatus.AVAILABLE
            trip.driver.assigned_vehicle = None
            trip.driver.save(update_fields=["status", "availability_status", "assigned_vehicle", "updated_at"])
        for order in TripWorkflowService._orders_on_trip(trip):
            order.status = order.Status.COMPLETED
            if not order.shipments.filter(trip__isnull=False).exclude(trip=trip).exists():
                order.assigned_trip = None
                order.assigned_vehicle = None
                order.assigned_driver = None
                order.save(update_fields=["status", "assigned_trip", "assigned_vehicle", "assigned_driver", "updated_at"])
            else:
                order.save(update_fields=["status", "updated_at"])
        notify_customer_delivery_confirmed(trip)
        invalidate_dashboard_cache()
        return trip


def add_shipment(*, trip, order, customer, quantity, carriage_type=Shipment.CarriageType.OTHER, container_number=""):
    shipment = Shipment(
        trip=trip,
        order=order,
        customer=order.customer,
        weight_kg=quantity,
        carriage_type=carriage_type,
        container_number=container_number,
        status=Shipment.Status.ASSIGNED if trip else Shipment.Status.PENDING,
        sender_name="ZALA Terminal",
    )
    shipment.full_clean()
    shipment.save()
    trip.full_clean()
    TripWorkflowService.sync_trip_shipments(trip=trip, shipments=trip.shipments.all())
    return shipment


def reject_trip(*, trip):
    return TripWorkflowService.reject_trip(trip=trip)


def add_revenue(*, trip, revenue_type_name, amount, created_by=None):
    revenue_type, _ = RevenueType.objects.get_or_create(name=revenue_type_name)
    return Revenue.objects.create(trip=trip, type=revenue_type, amount=amount, created_by=created_by)


def request_allowance(*, trip, driver, amount, created_by=None):
    return DriverAllowance.objects.create(
        trip=trip,
        driver=driver,
        amount=amount,
        created_by=created_by,
    )
