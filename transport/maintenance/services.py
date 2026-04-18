from django.db import models
from django.db.models import Sum
from django.utils import timezone

from transport.finance.models import ExpenseType, ensure_default_expense_types

from .models import MaintenanceRecord


def near_service_alerts(buffer_km=500):
    from transport.vehicles.models import Vehicle

    return Vehicle.objects.filter(current_odometer__gte=models.F("next_service_km") - buffer_km).order_by("plate_number")


def monthly_maintenance_cost(month_start, month_end):
    return (
        MaintenanceRecord.objects.filter(service_date__gte=month_start, service_date__lte=month_end)
        .aggregate(total=Sum("cost"))
        .get("total")
        or 0
    )


def total_downtime_days(month_start, month_end):
    return (
        MaintenanceRecord.objects.filter(service_date__gte=month_start, service_date__lte=month_end)
        .aggregate(total=Sum("downtime_days"))
        .get("total")
        or 0
    )


def _maintenance_description(record):
    description = f"{record.service_type} at {record.workshop}"
    if record.trip_id:
        description += f" for trip {record.trip.order_number}"
    return description


def sync_maintenance_expense(record):
    ensure_default_expense_types()

    if record.status != MaintenanceRecord.Status.APPROVED:
        if record.expense_id:
            expense = record.expense
            record.expense = None
            record.save(update_fields=["expense", "updated_at"])
            expense.delete()
        return None

    expense_type = ExpenseType.objects.get(name="Maintenance")
    expense = record.expense
    if expense is None:
        from transport.finance.models import Expense

        expense = Expense()

    expense.trip = record.trip
    expense.vehicle = record.vehicle
    expense.type = expense_type
    expense.category = expense_type.name
    expense.status = "APPROVED"
    expense.amount = record.cost
    expense.expense_date = record.service_date
    expense.description = _maintenance_description(record)
    expense.created_by = record.created_by or record.approved_by
    expense.save()

    if record.expense_id != expense.pk:
        record.expense = expense
        record.save(update_fields=["expense", "updated_at"])
    return expense


def approve_maintenance_record(record, approved_by):
    record.status = MaintenanceRecord.Status.APPROVED
    record.approved_by = approved_by
    record.approved_at = timezone.now()
    record.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    sync_maintenance_expense(record)
    return record
