import json
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from transport.finance.models import Expense
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle


ZERO = Decimal("0")
HIGH_CONSUMPTION_MULTIPLIER = Decimal("1.5")
FUEL_EXPENSE_FILTER = Q(type__name__iexact="Fuel") | Q(category__iexact="Fuel")


def quantize_metric(value, places="0.01"):
    if value is None:
        return None
    return Decimal(value).quantize(Decimal(places), rounding=ROUND_HALF_UP)


def base_fuel_expense_queryset():
    return (
        Expense.objects.filter(FUEL_EXPENSE_FILTER)
        .select_related("type", "trip__vehicle", "trip__driver", "trip__route", "vehicle")
        .order_by("-expense_date", "-created_at")
    )


def fuel_filter_options():
    fuel_queryset = base_fuel_expense_queryset()
    vehicles = (
        Vehicle.objects.filter(Q(trips__expenses__in=fuel_queryset) | Q(finance_expenses__in=fuel_queryset))
        .distinct()
        .order_by("plate_number")
    )
    trips = (
        Trip.objects.filter(expenses__in=fuel_queryset)
        .select_related("route", "vehicle")
        .distinct()
        .order_by("-created_at")
    )
    return {"vehicles": vehicles, "trips": trips}


def apply_fuel_filters(queryset, filters):
    vehicle_id = (filters.get("vehicle") or "").strip()
    trip_id = (filters.get("trip") or "").strip()
    date_from = (filters.get("date_from") or "").strip()
    date_to = (filters.get("date_to") or "").strip()

    if vehicle_id:
        queryset = queryset.filter(Q(trip__vehicle_id=vehicle_id) | Q(vehicle_id=vehicle_id))
    if trip_id:
        queryset = queryset.filter(trip_id=trip_id)
    if date_from:
        queryset = queryset.filter(expense_date__gte=date_from)
    if date_to:
        queryset = queryset.filter(expense_date__lte=date_to)
    return queryset


def weighted_average_fuel_price(queryset):
    base_queryset = Expense.objects.filter(pk__in=queryset.values("pk"))
    totals = base_queryset.filter(liters__gt=0).aggregate(total_cost=Sum("amount"), total_liters=Sum("liters"))
    total_cost = totals.get("total_cost") or ZERO
    total_liters = totals.get("total_liters") or ZERO
    if not total_liters:
        return ZERO
    return quantize_metric(total_cost / total_liters, "0.0001")


def _trip_distance(trip):
    if not trip:
        return ZERO
    route_distance = getattr(getattr(trip, "route", None), "distance_km", None)
    if route_distance and route_distance > 0:
        return Decimal(route_distance)
    return Decimal(trip.distance or ZERO)


def _estimate_liters(expense, average_price):
    liters = expense.liters
    if liters and liters > 0:
        return Decimal(liters), False
    if average_price and average_price > 0:
        return quantize_metric(Decimal(expense.amount or ZERO) / average_price), True
    return ZERO, False


def build_fuel_records(queryset, average_price=None):
    average_price = average_price if average_price is not None else weighted_average_fuel_price(queryset)
    records = []
    for expense in queryset:
        trip = expense.trip
        vehicle = trip.vehicle if trip_id_available(trip) else expense.vehicle
        driver = trip.driver if trip_id_available(trip) else None
        liters, liters_estimated = _estimate_liters(expense, average_price)
        distance = _trip_distance(trip)
        fuel_per_km = quantize_metric(liters / distance, "0.0001") if liters > 0 and distance > 0 else None
        cost_per_km = quantize_metric(Decimal(expense.amount or ZERO) / distance, "0.0001") if distance > 0 else None
        route_label = (
            f"{trip.route.origin} -> {trip.route.destination}"
            if trip_id_available(trip) and trip.route_id
            else "-"
        )
        records.append(
            {
                "expense": expense,
                "trip": trip,
                "vehicle": vehicle,
                "driver": driver,
                "date": expense.expense_date,
                "cost": Decimal(expense.amount or ZERO),
                "liters": liters,
                "liters_estimated": liters_estimated,
                "distance": distance,
                "fuel_per_km": fuel_per_km,
                "cost_per_km": cost_per_km,
                "route_label": route_label,
            }
        )
    return records


def trip_id_available(trip):
    return trip is not None and getattr(trip, "pk", None) is not None


def build_global_stats(records):
    total_cost = sum((record["cost"] for record in records), ZERO)
    total_liters = sum((record["liters"] for record in records), ZERO)
    total_distance = sum((record["distance"] for record in records), ZERO)
    average_fuel_per_km = quantize_metric(total_liters / total_distance, "0.0001") if total_distance > 0 and total_liters > 0 else ZERO
    average_cost_per_km = quantize_metric(total_cost / total_distance, "0.0001") if total_distance > 0 else ZERO
    return {
        "total_cost": total_cost,
        "total_liters": total_liters,
        "total_distance": total_distance,
        "average_fuel_per_km": average_fuel_per_km,
        "average_cost_per_km": average_cost_per_km,
    }


def build_vehicle_summary(records):
    grouped = defaultdict(
        lambda: {
            "vehicle": None,
            "total_fuel_used": ZERO,
            "total_cost": ZERO,
            "total_distance": ZERO,
            "trips_count": 0,
            "trip_ids": set(),
        }
    )

    for record in records:
        vehicle = record["vehicle"]
        if vehicle is None:
            continue
        item = grouped[vehicle.pk]
        item["vehicle"] = vehicle
        item["total_fuel_used"] += record["liters"]
        item["total_cost"] += record["cost"]
        item["total_distance"] += record["distance"]
        if record["trip"] and record["trip"].pk not in item["trip_ids"]:
            item["trip_ids"].add(record["trip"].pk)
            item["trips_count"] += 1

    summary = []
    for item in grouped.values():
        total_fuel = item["total_fuel_used"]
        total_distance = item["total_distance"]
        item["average_fuel_per_km"] = quantize_metric(total_fuel / total_distance, "0.0001") if total_fuel > 0 and total_distance > 0 else ZERO
        item["km_per_liter"] = quantize_metric(total_distance / total_fuel, "0.01") if total_fuel > 0 and total_distance > 0 else ZERO
        item.pop("trip_ids", None)
        summary.append(item)

    summary.sort(key=lambda row: (row["total_cost"], row["total_fuel_used"]), reverse=True)
    return summary


def build_trip_analysis(records):
    trips_with_fuel_usage = [record for record in records if record["liters"] > 0]
    trips_with_cost_per_km = [record for record in records if record["cost_per_km"] is not None]

    highest_fuel_usage = sorted(trips_with_fuel_usage, key=lambda row: row["liters"], reverse=True)[:5]
    highest_cost_per_km = sorted(
        trips_with_cost_per_km,
        key=lambda row: row["cost_per_km"] or ZERO,
        reverse=True,
    )[:5]
    return {
        "highest_fuel_usage": highest_fuel_usage,
        "highest_cost_per_km": highest_cost_per_km,
    }


def build_loss_detection(records):
    usable_records = [record for record in records if record["fuel_per_km"] is not None]
    if not usable_records:
        return {"average_fuel_per_km": ZERO, "threshold": ZERO, "flagged_records": []}

    average_fuel_per_km = quantize_metric(
        sum((record["fuel_per_km"] for record in usable_records), ZERO) / Decimal(len(usable_records)),
        "0.0001",
    )
    threshold = quantize_metric(average_fuel_per_km * HIGH_CONSUMPTION_MULTIPLIER, "0.0001")
    flagged_records = [record for record in usable_records if (record["fuel_per_km"] or ZERO) > threshold]
    return {
        "average_fuel_per_km": average_fuel_per_km,
        "threshold": threshold,
        "flagged_records": flagged_records,
    }


def build_chart_data(queryset, records):
    monthly_cost = (
        queryset.annotate(period=TruncMonth("expense_date"))
        .values("period")
        .annotate(total_cost=Sum("amount"))
        .order_by("period")
    )
    monthly_liters_map = defaultdict(Decimal)
    for record in records:
        if not record["date"]:
            continue
        period_key = record["date"].replace(day=1)
        monthly_liters_map[period_key] += record["liters"]

    monthly_labels = []
    monthly_cost_values = []
    monthly_liters_values = []
    for row in monthly_cost:
        period = row["period"].date() if hasattr(row["period"], "date") else row["period"]
        monthly_labels.append(period.strftime("%b %Y"))
        monthly_cost_values.append(float(row["total_cost"] or 0))
        monthly_liters_values.append(float(monthly_liters_map.get(period, ZERO)))

    vehicle_usage = defaultdict(lambda: {"label": "", "liters": ZERO})
    fuel_type_usage = defaultdict(lambda: ZERO)
    for record in records:
        vehicle = record["vehicle"]
        if vehicle is None:
            continue
        vehicle_usage[vehicle.pk]["label"] = vehicle.plate_number
        vehicle_usage[vehicle.pk]["liters"] += record["liters"]
        fuel_type_label = vehicle.get_fuel_type_display() if getattr(vehicle, "fuel_type", None) else "Unknown"
        fuel_type_usage[fuel_type_label] += record["liters"]

    vehicle_rows = sorted(vehicle_usage.values(), key=lambda row: row["liters"], reverse=True)[:8]
    fuel_type_rows = sorted(fuel_type_usage.items(), key=lambda row: row[1], reverse=True)
    return {
        "monthly_labels_json": json.dumps(monthly_labels),
        "monthly_cost_values_json": json.dumps(monthly_cost_values),
        "monthly_liters_values_json": json.dumps(monthly_liters_values),
        "vehicle_labels_json": json.dumps([row["label"] for row in vehicle_rows]),
        "vehicle_liters_values_json": json.dumps([float(row["liters"]) for row in vehicle_rows]),
        "fuel_type_labels_json": json.dumps([row[0] for row in fuel_type_rows]),
        "fuel_type_liters_values_json": json.dumps([float(row[1]) for row in fuel_type_rows]),
    }
