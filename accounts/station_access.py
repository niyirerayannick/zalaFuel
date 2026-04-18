"""
Station-scoped data access for multi-site fuel operations.

Rules (production-oriented):
- Superusers, Admin group, and Accountant group: all active stations (finance/reporting).
- Station Manager, Supervisor, Pump Attendant: only ``user.assigned_station`` when set.
- Authenticated staff with no assignment and no global role: no station-scoped data (empty queryset).
"""

from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from stations.models import Station

from .rbac import SystemGroup, user_has_role


def user_sees_all_stations(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user_has_role(user, SystemGroup.ADMIN, SystemGroup.ACCOUNTANT)


def visible_stations(user) -> QuerySet[Station]:
    """Active stations the user may access."""
    qs = Station.objects.filter(is_active=True).order_by("name")
    if user_sees_all_stations(user):
        return qs
    sid = getattr(user, "assigned_station_id", None)
    if sid:
        return qs.filter(pk=sid)
    return Station.objects.none()


def visible_station_ids(user) -> list:
    return list(visible_stations(user).values_list("pk", flat=True))


def require_station_access(user, station) -> None:
    """
    Raise PermissionDenied if user may not access this station.
    ``station`` may be a Station instance or primary key.
    """
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("Authentication required.")
    sid = station.pk if isinstance(station, Station) else station
    if sid is None:
        raise PermissionDenied("Station is required.")
    if user_sees_all_stations(user):
        if not Station.objects.filter(pk=sid, is_active=True).exists():
            raise PermissionDenied("Invalid or inactive station.")
        return
    if getattr(user, "assigned_station_id", None) == sid:
        return
    raise PermissionDenied("You do not have access to this station.")


def filter_by_visible_stations(
    queryset: QuerySet,
    user,
    *,
    field_path: str = "station_id",
) -> QuerySet:
    """Restrict a queryset to stations the user may see (``field_path`` dotted lookup)."""
    if user_sees_all_stations(user):
        return queryset
    ids = visible_station_ids(user)
    if not ids:
        return queryset.none()
    return queryset.filter(**{f"{field_path}__in": ids})


def user_can_access_shift(user, shift) -> bool:
    """Read access: station scope + attendants only see their own shifts unless manager-level."""
    from sales.models import ShiftSession

    if not shift or not isinstance(shift, ShiftSession):
        return False
    try:
        require_station_access(user, shift.station_id)
    except PermissionDenied:
        return False
    if user_sees_all_stations(user):
        return True
    if user_has_role(user, SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR):
        return True
    if user_has_role(user, SystemGroup.PUMP_ATTENDANT):
        return shift.attendant_id == getattr(user, "pk", None)
    return False


def user_can_close_shift(user, shift) -> bool:
    from sales.models import ShiftSession

    if not shift or not isinstance(shift, ShiftSession):
        return False
    try:
        require_station_access(user, shift.station_id)
    except PermissionDenied:
        return False
    if getattr(user, "is_superuser", False) or user_has_role(user, SystemGroup.ADMIN):
        return True
    if user_has_role(user, SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR):
        return True
    if user_has_role(user, SystemGroup.PUMP_ATTENDANT):
        return shift.attendant_id == getattr(user, "pk", None)
    return False


def user_can_edit_station(user, station) -> bool:
    """Create/update station master data (not pump/tank configuration)."""
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or user_has_role(user, SystemGroup.ADMIN):
        return True
    if user_has_role(user, SystemGroup.STATION_MANAGER):
        sid = station.pk if isinstance(station, Station) else station
        return getattr(user, "assigned_station_id", None) == sid
    return False


def user_can_open_shift_for(user, *, station, attendant) -> bool:
    """Opening uses a chosen attendant; managers may open for others at their station."""
    if not user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.PUMP_ATTENDANT,
    ):
        return False
    try:
        require_station_access(user, station)
    except PermissionDenied:
        return False
    if getattr(user, "is_superuser", False) or user_has_role(user, SystemGroup.ADMIN):
        return True
    if user_has_role(user, SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR):
        return getattr(user, "assigned_station_id", None) == getattr(station, "pk", None)
    if user_has_role(user, SystemGroup.PUMP_ATTENDANT):
        return attendant.pk == user.pk and getattr(user, "assigned_station_id", None) == getattr(station, "pk", None)
    return False


def filter_shifts_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    """Station scope; pump attendants only see their own shifts."""
    queryset = filter_by_visible_stations(queryset, user, field_path="station_id")
    if user_sees_all_stations(user) or user_has_role(
        user, SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR, SystemGroup.ADMIN
    ):
        return queryset
    if user_has_role(user, SystemGroup.PUMP_ATTENDANT):
        return queryset.filter(attendant=user)
    return queryset.none()


def filter_tanks_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="station_id")


def filter_pumps_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="station_id")


def filter_nozzles_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="pump__station_id")


def filter_inventory_records_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="tank__station_id")


def filter_purchase_orders_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="station_id")


def filter_delivery_receipts_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    return filter_by_visible_stations(queryset, user, field_path="purchase_order__station_id")


def filter_fuel_sales_queryset_for_user(queryset: QuerySet, user) -> QuerySet:
    """``FuelSale`` rows visible to the user (station + attendant rules)."""
    queryset = filter_by_visible_stations(queryset, user, field_path="shift__station_id")
    if user_sees_all_stations(user) or user_has_role(
        user, SystemGroup.STATION_MANAGER, SystemGroup.SUPERVISOR, SystemGroup.ADMIN
    ):
        return queryset
    if user_has_role(user, SystemGroup.PUMP_ATTENDANT):
        return queryset.filter(shift__attendant=user)
    return queryset.none()
