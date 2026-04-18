import json
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.urls import reverse
from django.utils import timezone

from transport.customers.models import Customer
from transport.drivers.models import Driver
from transport.finance.models import Expense, Payment
from transport.fuel.models import FuelRequest, FuelStation
from transport.fuel.services import base_fuel_expense_queryset, build_fuel_records, weighted_average_fuel_price
from transport.maintenance.models import MaintenanceRecord
from transport.orders.models import Order
from transport.routes.models import Route
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle
from transport.messaging.models import DriverManagerMessage

User = get_user_model()

TIME_FILTER_OPTIONS = [
    {"key": "today", "label": "Today"},
    {"key": "week", "label": "This Week"},
    {"key": "month", "label": "This Month"},
    {"key": "year", "label": "This Year"},
    {"key": "all", "label": "All Time"},
]
VALID_RANGE_KEYS = {option["key"] for option in TIME_FILTER_OPTIONS}
NOTIFICATION_CACHE_TIMEOUT = 60


def invalidate_notification_cache_for_user(user_id):
    if not user_id:
        return
    for limit in (12, 50):
        try:
            cache.delete(f"transport.notifications.{user_id}.{limit}")
        except Exception:
            pass


def _notification_item(*, level, icon, title, message, link, timestamp):
    return {
        "level": level,
        "icon": icon,
        "title": title,
        "message": message,
        "link": link,
        "timestamp": timestamp,
        "timestamp_label": timezone.localtime(timestamp).strftime("%d %b %Y %H:%M")
        if timezone.is_aware(timestamp)
        else timestamp.strftime("%d %b %Y"),
    }


def user_notification_payload(user, *, limit=12):
    if not getattr(user, "is_authenticated", False):
        return {
            "notifications": [],
            "notification_count": 0,
            "support_chat_unread_count": 0,
        }

    cache_key = f"transport.notifications.{user.pk}.{limit}"
    try:
        cached_payload = cache.get(cache_key)
    except Exception:
        cached_payload = None
    if cached_payload is not None:
        return cached_payload

    notifications = []
    today = timezone.localdate()
    now = timezone.now()
    expires_soon = today + timedelta(days=30)

    unread_support_qs = (
        DriverManagerMessage.objects.filter(recipient=user, read_at__isnull=True)
        .exclude(sender=user)
        .select_related("sender")
        .order_by("-created_at")
    )
    support_chat_unread_count = unread_support_qs.count()

    for message in unread_support_qs[:6]:
        sender_name = message.sender.full_name or message.sender.email
        notifications.append(
            _notification_item(
                level="info",
                icon="chat",
                title=f"New message from {sender_name}",
                message=message.body[:120],
                link=reverse("transport:analytics:support")
                if getattr(user, "role", "") in {"superadmin", "admin", "manager"}
                else reverse("transport:analytics:client-support"),
                timestamp=message.created_at,
            )
        )

    if getattr(user, "role", "") in {"superadmin", "admin", "manager"}:
        for vehicle in Vehicle.objects.filter(status=Vehicle.VehicleStatus.MAINTENANCE).order_by("-updated_at")[:5]:
            notifications.append(
                _notification_item(
                    level="warning",
                    icon="build",
                    title="Vehicle under maintenance",
                    message=f"{vehicle.plate_number} is currently being serviced.",
                    link=reverse("transport:vehicles:detail", args=[vehicle.pk]),
                    timestamp=vehicle.updated_at or vehicle.created_at,
                )
            )

        for vehicle in Vehicle.objects.filter(
            insurance_expiry__lte=expires_soon,
            insurance_expiry__gte=today,
        ).order_by("insurance_expiry")[:5]:
            notifications.append(
                _notification_item(
                    level="danger",
                    icon="shield",
                    title="Insurance expiry approaching",
                    message=f"{vehicle.plate_number} insurance expires on {vehicle.insurance_expiry:%d %b %Y}.",
                    link=reverse("transport:vehicles:detail", args=[vehicle.pk]),
                    timestamp=timezone.make_aware(datetime.combine(vehicle.insurance_expiry, time.min)),
                )
            )

        for vehicle in Vehicle.objects.filter(
            inspection_expiry__lte=expires_soon,
            inspection_expiry__gte=today,
        ).order_by("inspection_expiry")[:5]:
            notifications.append(
                _notification_item(
                    level="danger",
                    icon="fact_check",
                    title="Inspection expiry approaching",
                    message=f"{vehicle.plate_number} inspection expires on {vehicle.inspection_expiry:%d %b %Y}.",
                    link=reverse("transport:vehicles:detail", args=[vehicle.pk]),
                    timestamp=timezone.make_aware(datetime.combine(vehicle.inspection_expiry, time.min)),
                )
            )

        for driver in Driver.objects.filter(
            license_expiry__lte=expires_soon,
            license_expiry__gte=today,
        ).order_by("license_expiry")[:5]:
            notifications.append(
                _notification_item(
                    level="warning",
                    icon="badge",
                    title="Driver license expiry approaching",
                    message=f"{driver.name} license expires on {driver.license_expiry:%d %b %Y}.",
                    link=reverse("transport:drivers:detail", args=[driver.pk]),
                    timestamp=timezone.make_aware(datetime.combine(driver.license_expiry, time.min)),
                )
            )

        overdue_cutoff = now - timedelta(days=7)
        for trip in Trip.objects.filter(
            status=Trip.TripStatus.IN_TRANSIT,
            updated_at__lte=overdue_cutoff,
        ).select_related("route")[:5]:
            notifications.append(
                _notification_item(
                    level="warning",
                    icon="schedule",
                    title="Trip needs attention",
                    message=f"{trip.order_number} has been in transit for more than 7 days.",
                    link=reverse("transport:trips:detail", args=[trip.pk]),
                    timestamp=trip.updated_at,
                )
            )

    notifications.sort(key=lambda item: item["timestamp"], reverse=True)
    limited_notifications = notifications[:limit]
    payload = {
        "notifications": limited_notifications,
        "notification_count": len(notifications),
        "support_chat_unread_count": support_chat_unread_count,
    }
    try:
        cache.set(cache_key, payload, NOTIFICATION_CACHE_TIMEOUT)
    except Exception:
        pass
    return payload


def _fuel_liters_for_range(range_config):
    fuel_expense_queryset = apply_date_range(
        base_fuel_expense_queryset(),
        "expense_date",
        range_config,
    )
    average_price = weighted_average_fuel_price(fuel_expense_queryset)
    records = build_fuel_records(fuel_expense_queryset, average_price=average_price)
    return sum((record["liters"] for record in records), Decimal("0"))


def invalidate_dashboard_cache():
    for role in ("superadmin", "admin", "manager"):
        for range_key in VALID_RANGE_KEYS:
            try:
                cache.delete(f"dashboard_context_{role}_{range_key}")
            except Exception:
                pass


def normalize_range_key(range_key):
    return range_key if range_key in VALID_RANGE_KEYS else "month"


def resolve_time_range(range_key):
    range_key = normalize_range_key(range_key)
    today = timezone.localdate()

    if range_key == "today":
        start_date = end_date = today
        label = "Today"
    elif range_key == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        label = "This Week"
    elif range_key == "month":
        start_date = today.replace(day=1)
        end_date = today
        label = "This Month"
    elif range_key == "year":
        start_date = today.replace(month=1, day=1)
        end_date = today
        label = "This Year"
    else:
        start_date = None
        end_date = None
        label = "All Time"

    return {
        "key": range_key,
        "label": label,
        "start_date": start_date,
        "end_date": end_date,
        "today": today,
    }


def apply_date_range(queryset, lookup, range_config):
    start_date = range_config["start_date"]
    end_date = range_config["end_date"]
    if start_date:
        queryset = queryset.filter(**{f"{lookup}__gte": start_date})
    if end_date:
        queryset = queryset.filter(**{f"{lookup}__lte": end_date})
    return queryset


def _chart_bucket(range_key):
    return TruncDate if range_key in {"today", "week"} else TruncMonth


def _chart_label(value, range_key):
    if not value:
        return ""
    if range_key in {"today", "week"}:
        return value.strftime("%d %b")
    return value.strftime("%b %Y")


def executive_dashboard_metrics(range_key="month"):
    """Core KPI cards for the selected time range."""
    range_config = resolve_time_range(range_key)

    vehicle_queryset = apply_date_range(Vehicle.objects.all(), "created_at__date", range_config)
    driver_queryset = apply_date_range(Driver.objects.all(), "created_at__date", range_config)
    order_queryset = apply_date_range(Order.objects.all(), "created_at__date", range_config)
    user_queryset = apply_date_range(User.objects.filter(is_active=True), "created_at__date", range_config)
    trip_queryset = apply_date_range(Trip.objects.all(), "created_at__date", range_config)
    active_trip_queryset = apply_date_range(
        Trip.objects.filter(status__in=[Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT]),
        "updated_at__date",
        range_config,
    )
    active_trips = active_trip_queryset.count()
    available_vehicles = vehicle_queryset.filter(status=Vehicle.VehicleStatus.AVAILABLE).count()
    vehicles_in_maintenance = vehicle_queryset.filter(status=Vehicle.VehicleStatus.MAINTENANCE).count()
    active_drivers = driver_queryset.filter(status=Driver.DriverStatus.ASSIGNED).count()
    total_vehicles = vehicle_queryset.count()
    total_orders = order_queryset.count()
    total_drivers = driver_queryset.count()
    total_trips = trip_queryset.count()
    total_users = user_queryset.count()

    trip_totals = trip_queryset.aggregate(
        monthly_revenue=Sum("revenue"),
        monthly_fuel_cost=Sum("fuel_cost"),
        net_profit=Sum("profit"),
    )
    maintenance_total = (
        apply_date_range(MaintenanceRecord.objects.all(), "service_date", range_config)
        .aggregate(total=Sum("cost"))
        .get("total")
        or Decimal("0")
    )

    fleet_total = vehicle_queryset.count() or 1
    busy_vehicles = vehicle_queryset.filter(status=Vehicle.VehicleStatus.ASSIGNED).count()
    fleet_utilization = round((busy_vehicles / fleet_total) * 100, 2)

    due_soon_vehicles = vehicle_queryset.filter(
        next_service_km__gt=0,
        current_odometer__gte=F("next_service_km") - 1000,
    )
    fuel_for_range = _fuel_liters_for_range(range_config)

    expires_soon = range_config["today"] + timedelta(days=30)
    insurance_exp = vehicle_queryset.filter(
        insurance_expiry__lte=expires_soon,
        insurance_expiry__gte=range_config["today"],
    )
    inspection_exp = vehicle_queryset.filter(
        inspection_expiry__lte=expires_soon,
        inspection_expiry__gte=range_config["today"],
    )
    license_exp = driver_queryset.filter(
        license_expiry__lte=expires_soon,
        license_expiry__gte=range_config["today"],
    )
    overdue_cutoff = timezone.now() - timedelta(days=7)
    overdue_trips = active_trip_queryset.filter(updated_at__lte=overdue_cutoff)
    active_alerts = vehicles_in_maintenance + insurance_exp.count() + inspection_exp.count() + license_exp.count() + overdue_trips.count()

    return {
        "total_vehicles": total_vehicles,
        "total_orders": total_orders,
        "total_drivers": total_drivers,
        "total_trips": total_trips,
        "active_trips": active_trips,
        "available_vehicles": available_vehicles,
        "active_drivers": active_drivers,
        "total_users": total_users,
        "maintenance_due": due_soon_vehicles.count(),
        "vehicles_in_maintenance": vehicles_in_maintenance,
        "fuel_this_month_litres": fuel_for_range,
        "active_alerts": active_alerts,
        "monthly_revenue": trip_totals.get("monthly_revenue") or Decimal("0"),
        "monthly_fuel_cost": trip_totals.get("monthly_fuel_cost") or Decimal("0"),
        "monthly_maintenance_cost": maintenance_total,
        "net_profit": trip_totals.get("net_profit") or Decimal("0"),
        "fleet_utilization_percent": fleet_utilization,
    }


def full_dashboard_context(range_key="month"):
    """Return everything needed for the comprehensive dashboard template."""
    range_config = resolve_time_range(range_key)
    selected_range = range_config["key"]
    now = timezone.now()
    today = range_config["today"]
    twelve_months_ago = (today - timedelta(days=365)).replace(day=1)

    metrics = executive_dashboard_metrics(selected_range)

    vehicle_queryset = apply_date_range(Vehicle.objects.all(), "created_at__date", range_config)
    driver_queryset = apply_date_range(Driver.objects.all(), "created_at__date", range_config)
    customer_queryset = apply_date_range(Customer.objects.all(), "created_at__date", range_config)
    trip_queryset = apply_date_range(Trip.objects.all(), "created_at__date", range_config)
    active_trip_queryset = apply_date_range(
        Trip.objects.filter(status__in=[Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT]),
        "updated_at__date",
        range_config,
    )
    maintenance_queryset = apply_date_range(MaintenanceRecord.objects.all(), "service_date", range_config)
    fuel_queryset = apply_date_range(FuelRequest.objects.all(), "created_at__date", range_config)

    total_vehicles = vehicle_queryset.count()
    active_vehicles = vehicle_queryset.filter(
        status__in=[Vehicle.VehicleStatus.AVAILABLE, Vehicle.VehicleStatus.ASSIGNED]
    ).count()
    total_drivers = driver_queryset.count()
    total_customers = customer_queryset.count()
    total_routes = Route.objects.count()
    total_trips = trip_queryset.count()
    completed_trips_total = trip_queryset.filter(
        status__in=[Trip.TripStatus.DELIVERED, Trip.TripStatus.CLOSED]
    ).count()
    total_fuel_stations = FuelStation.objects.count()
    total_fuel_logs = fuel_queryset.count()

    fleet_by_status = dict(
        vehicle_queryset.values_list("status").annotate(c=Count("id")).values_list("status", "c")
    )
    fleet_by_type = list(
        vehicle_queryset.values("vehicle_type").annotate(count=Count("id")).order_by("-count")
    )

    driver_by_status = dict(
        driver_queryset.values_list("status").annotate(c=Count("id")).values_list("status", "c")
    )

    trip_by_status = list(
        trip_queryset.values("status").annotate(count=Count("id")).order_by("status")
    )
    period_trips = total_trips
    delivered_trips = trip_queryset.filter(status=Trip.TripStatus.DELIVERED).count()
    closed_trips = trip_queryset.filter(status=Trip.TripStatus.CLOSED).count()

    fin = trip_queryset.aggregate(
        all_revenue=Sum("revenue"),
        all_cost=Sum("total_cost"),
        all_profit=Sum("profit"),
        all_fuel_cost=Sum("fuel_cost"),
        all_distance=Sum("distance"),
    )
    total_revenue = fin["all_revenue"] or Decimal("0")
    total_cost = fin["all_cost"] or Decimal("0")
    total_profit = fin["all_profit"] or Decimal("0")
    total_fuel_cost = fin["all_fuel_cost"] or Decimal("0")
    total_distance = fin["all_distance"] or Decimal("0")
    total_payments = Payment.objects.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_expenses = Expense.objects.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_maintenance_cost = maintenance_queryset.aggregate(s=Sum("cost"))["s"] or Decimal("0")
    average_fuel_request = fuel_queryset.aggregate(avg=Avg("amount"))["avg"] or Decimal("0")
    dashboard_profit_summary = total_revenue - total_expenses

    chart_trip_queryset = trip_queryset if selected_range != "all" else Trip.objects.filter(created_at__date__gte=twelve_months_ago)
    chart_fuel_queryset = fuel_queryset if selected_range != "all" else FuelRequest.objects.filter(created_at__date__gte=twelve_months_ago)
    bucket = _chart_bucket(selected_range)

    trip_trend = list(
        chart_trip_queryset.annotate(period=bucket("created_at"))
        .values("period")
        .annotate(
            revenue=Sum("revenue"),
            cost=Sum("total_cost"),
            profit=Sum("profit"),
            count=Count("id"),
        )
        .order_by("period")
    )
    trend_labels = json.dumps([_chart_label(item["period"], selected_range) for item in trip_trend])
    trend_revenue = json.dumps([float(item["revenue"] or 0) for item in trip_trend])
    trend_cost = json.dumps([float(item["cost"] or 0) for item in trip_trend])
    trend_profit = json.dumps([float(item["profit"] or 0) for item in trip_trend])
    trend_count = json.dumps([item["count"] for item in trip_trend])

    fuel_trend = list(
        chart_fuel_queryset.annotate(period=bucket("created_at"))
        .values("period")
        .annotate(total_amount=Sum("amount"), request_count=Count("id"))
        .order_by("period")
    )
    fuel_labels = json.dumps([_chart_label(item["period"], selected_range) for item in fuel_trend])
    fuel_amounts = json.dumps([float(item["total_amount"] or 0) for item in fuel_trend])
    fuel_counts = json.dumps([item["request_count"] for item in fuel_trend])

    status_labels = json.dumps([item["status"] for item in trip_by_status])
    status_counts = json.dumps([item["count"] for item in trip_by_status])
    vtype_labels = json.dumps([item["vehicle_type"] or "Unknown" for item in fleet_by_type])
    vtype_counts = json.dumps([item["count"] for item in fleet_by_type])

    top_customers = list(
        trip_queryset.values("customer__company_name")
        .annotate(revenue=Sum("revenue"), trips=Count("id"))
        .order_by("-revenue")[:5]
    )
    top_routes = list(
        trip_queryset.values("route__origin", "route__destination")
        .annotate(trips=Count("id"), revenue=Sum("revenue"))
        .order_by("-trips")[:5]
    )

    alerts = []
    maint_vehicles = Vehicle.objects.filter(status=Vehicle.VehicleStatus.MAINTENANCE)
    for vehicle in maint_vehicles[:5]:
        alerts.append({
            "type": "warning",
            "icon": "wrench",
            "message": f"{vehicle.plate_number} is in maintenance",
            "link": f"/transport/vehicles/{vehicle.pk}/",
        })

    expires_soon = today + timedelta(days=30)
    insurance_exp = Vehicle.objects.filter(insurance_expiry__lte=expires_soon, insurance_expiry__gte=today)
    for vehicle in insurance_exp[:5]:
        alerts.append({
            "type": "danger",
            "icon": "shield",
            "message": f"{vehicle.plate_number} insurance expires {vehicle.insurance_expiry.strftime('%d %b %Y')}",
            "link": f"/transport/vehicles/{vehicle.pk}/",
        })

    inspection_exp = Vehicle.objects.filter(inspection_expiry__lte=expires_soon, inspection_expiry__gte=today)
    for vehicle in inspection_exp[:5]:
        alerts.append({
            "type": "danger",
            "icon": "clipboard",
            "message": f"{vehicle.plate_number} inspection expires {vehicle.inspection_expiry.strftime('%d %b %Y')}",
            "link": f"/transport/vehicles/{vehicle.pk}/",
        })

    license_exp = Driver.objects.filter(license_expiry__lte=expires_soon, license_expiry__gte=today)
    for driver in license_exp[:5]:
        alerts.append({
            "type": "danger",
            "icon": "id-card",
            "message": f"Driver {driver} license expires {driver.license_expiry.strftime('%d %b %Y')}",
            "link": f"/transport/drivers/{driver.pk}/",
        })

    overdue_cutoff = now - timedelta(days=7)
    overdue_trips = Trip.objects.filter(status=Trip.TripStatus.IN_TRANSIT, updated_at__lte=overdue_cutoff)
    for trip in overdue_trips[:5]:
        alerts.append({
            "type": "warning",
            "icon": "clock",
            "message": f"Trip {trip.order_number} in transit over 7 days",
            "link": f"/transport/trips/{trip.pk}/",
        })

    recent_trips = trip_queryset.select_related("customer", "vehicle", "driver", "route").order_by("-created_at")[:10]
    recent_maintenance = maintenance_queryset.select_related("vehicle").order_by("-service_date")[:5]
    recent_fuel = fuel_queryset.select_related("trip", "station").order_by("-created_at")[:5]
    recent_payments = Payment.objects.select_related("trip").order_by("-payment_date")[:5]

    active_trip_rows = active_trip_queryset.select_related("vehicle", "driver", "route", "customer").order_by("-updated_at")[:5]
    upcoming_trip_rows = trip_queryset.select_related("vehicle", "driver", "route", "customer").filter(
        status__in=[Trip.TripStatus.DRAFT, Trip.TripStatus.APPROVED]
    ).order_by("-created_at")[:5]
    vehicle_status_rows = vehicle_queryset.order_by("plate_number")[:8]

    maintenance_alerts = []
    due_soon_vehicles = Vehicle.objects.filter(
        next_service_km__gt=0,
        current_odometer__gte=F("next_service_km") - 1000,
    ).order_by("next_service_km")[:6]
    for vehicle in due_soon_vehicles:
        maintenance_alerts.append({
            "plate_number": vehicle.plate_number,
            "message": f"Service due near {vehicle.next_service_km:,} km",
            "severity": "warning" if vehicle.current_odometer < vehicle.next_service_km else "danger",
            "detail": f"Current odometer: {vehicle.current_odometer:,.0f} km",
            "link": f"/transport/vehicles/{vehicle.pk}/",
        })
    for record in recent_maintenance[:3]:
        maintenance_alerts.append({
            "plate_number": record.vehicle.plate_number,
            "message": f"{record.service_type} on {record.service_date.strftime('%d %b %Y')}",
            "severity": "info" if record.downtime_days == 0 else "warning",
            "detail": f"Downtime: {record.downtime_days} day(s)",
            "link": f"/transport/maintenance/{record.pk}/",
        })

    recent_activities = []
    for trip in recent_trips[:4]:
        recent_activities.append({
            "type": "trip",
            "title": f"Trip {trip.order_number} created",
            "subtitle": f"{trip.customer.company_name} - {trip.route.origin} to {trip.route.destination}",
            "timestamp": trip.created_at,
            "link": f"/transport/trips/{trip.pk}/",
        })
    for fuel in recent_fuel[:3]:
        recent_activities.append({
            "type": "fuel",
            "title": f"Fuel request added for {fuel.trip.order_number}",
            "subtitle": f"{fuel.station.name} - {fuel.amount}",
            "timestamp": fuel.created_at,
            "link": f"/transport/fuel/{fuel.pk}/",
        })
    for maintenance in recent_maintenance[:3]:
        recent_activities.append({
            "type": "maintenance",
            "title": f"Maintenance recorded for {maintenance.vehicle.plate_number}",
            "subtitle": f"{maintenance.service_type} - {maintenance.cost}",
            "timestamp": maintenance.created_at,
            "link": f"/transport/maintenance/{maintenance.pk}/",
        })
    recent_activities = sorted(recent_activities, key=lambda item: item["timestamp"], reverse=True)[:8]

    driver_trip_filter = {"trips__status": Trip.TripStatus.DELIVERED}
    if range_config["start_date"]:
        driver_trip_filter["trips__created_at__date__gte"] = range_config["start_date"]
    if range_config["end_date"]:
        driver_trip_filter["trips__created_at__date__lte"] = range_config["end_date"]

    top_drivers = list(
        Driver.objects.select_related("user")
        .annotate(trips_count=Count("trips", filter=Q(**driver_trip_filter)))
        .order_by("-trips_count")[:5]
    )

    driver_status_rows = []
    for driver in top_drivers:
        latest_trip = (
            Trip.objects.filter(driver=driver)
            .select_related("route")
            .order_by("-created_at")
            .first()
        )
        if driver.user_id:
            driver_name = driver.user.full_name or driver.user.get_username()
        else:
            driver_name = driver.name
        driver_status_rows.append(
            {
                "name": driver_name,
                "status": driver.get_status_display(),
                "trips_count": driver.trips_count,
                "route_text": (
                    f"{latest_trip.route.origin} to {latest_trip.route.destination}"
                    if latest_trip and latest_trip.route_id
                    else "No recent route"
                ),
            }
        )

    map_routes = [
        {
            "order_number": trip.order_number,
            "vehicle": trip.vehicle.plate_number,
            "route": f"{trip.route.origin} -> {trip.route.destination}",
            "status": trip.get_status_display(),
        }
        for trip in active_trip_rows
    ]

    return {
        "top_drivers": top_drivers,
        "metrics": metrics,
        "selected_range": selected_range,
        "selected_range_label": range_config["label"],
        "time_filter_options": TIME_FILTER_OPTIONS,
        "total_vehicles": total_vehicles,
        "active_vehicles": active_vehicles,
        "total_drivers": total_drivers,
        "total_customers": total_customers,
        "total_routes": total_routes,
        "total_trips": total_trips,
        "completed_trips_total": completed_trips_total,
        "total_fuel_stations": total_fuel_stations,
        "total_fuel_logs": total_fuel_logs,
        "average_fuel_request": average_fuel_request,
        "fleet_available": fleet_by_status.get("AVAILABLE", 0),
        "fleet_assigned": fleet_by_status.get("ASSIGNED", 0),
        "fleet_maintenance": fleet_by_status.get("MAINTENANCE", 0),
        "fleet_by_type": fleet_by_type,
        "drivers_available": driver_by_status.get("AVAILABLE", 0),
        "drivers_assigned": driver_by_status.get("ASSIGNED", 0),
        "drivers_on_leave": driver_by_status.get("LEAVE", 0),
        "trip_by_status": trip_by_status,
        "monthly_trips": period_trips,
        "delivered_trips": delivered_trips,
        "closed_trips": closed_trips,
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "dashboard_profit_summary": dashboard_profit_summary,
        "total_fuel_cost": total_fuel_cost,
        "total_distance": total_distance,
        "total_payments": total_payments,
        "total_expenses": total_expenses,
        "total_maintenance_cost": total_maintenance_cost,
        "trend_labels": trend_labels,
        "trend_revenue": trend_revenue,
        "trend_cost": trend_cost,
        "trend_profit": trend_profit,
        "trend_count": trend_count,
        "fuel_labels": fuel_labels,
        "fuel_amounts": fuel_amounts,
        "fuel_counts": fuel_counts,
        "status_labels": status_labels,
        "status_counts": status_counts,
        "vtype_labels": vtype_labels,
        "vtype_counts": vtype_counts,
        "top_customers": top_customers,
        "top_routes": top_routes,
        "alerts": alerts,
        "alert_count": len(alerts),
        "recent_trips": recent_trips,
        "recent_maintenance": recent_maintenance,
        "recent_fuel": recent_fuel,
        "recent_payments": recent_payments,
        "active_trip_rows": active_trip_rows,
        "upcoming_trip_rows": upcoming_trip_rows,
        "vehicle_status_rows": vehicle_status_rows,
        "driver_status_rows": driver_status_rows,
        "maintenance_alerts": maintenance_alerts[:6],
        "recent_activities": recent_activities,
        "map_routes": map_routes,
        "maintenance_due_count": Vehicle.objects.filter(
            next_service_km__gt=0,
            current_odometer__gte=F("next_service_km") - 1000,
        ).count(),
        "fuel_this_month_litres": _fuel_liters_for_range(
            {
                **range_config,
                "start_date": today.replace(day=1),
                "end_date": today,
            }
        ),
    }
