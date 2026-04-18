from django.contrib.auth import get_user_model


User = get_user_model()

SHIFT_STAFF_ROLES = (
    User.Role.ADMIN,
    User.Role.STATION_MANAGER,
    User.Role.SUPERVISOR,
    User.Role.PUMP_ATTENDANT,
)


def station_attendants(station_id):
    """Active operational staff assigned to a station."""
    if not station_id:
        return User.objects.none()
    return (
        User.objects.filter(
            is_active=True,
            assigned_station_id=station_id,
            role__in=SHIFT_STAFF_ROLES,
        )
        .order_by("full_name", "email")
    )
