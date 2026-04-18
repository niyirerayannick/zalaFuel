from .trip_service import (
    TripWorkflowError,
    TripWorkflowService,
    add_revenue,
    add_shipment,
    reject_trip as reject_trip_service,
    request_allowance,
)
from .models import Trip


def trip_queryset_for_operations():
    return (
        Trip.objects.select_related(
            "job",
            "customer",
            "commodity_type",
            "cargo_category",
            "route",
            "vehicle",
            "vehicle__owner",
            "driver",
        )
        .prefetch_related("shipments", "expenses", "revenues", "allowances")
        .order_by("-created_at")
    )


def create_trip(**kwargs):
    return TripWorkflowService.create_trip(**kwargs)


def sync_trip_shipments(*, trip, shipments):
    return TripWorkflowService.sync_trip_shipments(trip=trip, shipments=shipments)


def approve_trip(trip, approved_by):
    return TripWorkflowService.approve_trip(trip=trip, approved_by=approved_by)


def reject_trip(trip):
    return reject_trip_service(trip=trip)


def start_trip(trip):
    return TripWorkflowService.start_trip(trip=trip)


def complete_trip(trip):
    return TripWorkflowService.complete_trip(trip=trip)
