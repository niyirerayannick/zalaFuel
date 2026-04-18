from functools import wraps

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class SystemGroup:
    ADMIN = "Admin"
    STATION_MANAGER = "Station Manager"
    SUPERVISOR = "Supervisor"
    PUMP_ATTENDANT = "Pump Attendant"
    ACCOUNTANT = "Accountant"
    CUSTOMER = "Customer"

    STAFF = (ADMIN, STATION_MANAGER, SUPERVISOR, PUMP_ATTENDANT, ACCOUNTANT)
    OPERATIONS = (ADMIN, STATION_MANAGER, SUPERVISOR)
    ROLE_GROUPS = (ADMIN, STATION_MANAGER, SUPERVISOR, PUMP_ATTENDANT, ACCOUNTANT, CUSTOMER)


SYSTEM_ROLE_CHOICES = [
    ("superadmin", "SuperAdmin"),
    ("admin", "Admin"),
    ("station_manager", "Station Manager"),
    ("supervisor", "Supervisor"),
    ("pump_attendant", "Pump Attendant"),
    ("accountant", "Accountant"),
    ("client", "Customer"),
]

SYSTEM_ROLE_MAP = {internal: display for internal, display in SYSTEM_ROLE_CHOICES}


GROUP_PERMISSION_MAP = {
    SystemGroup.ADMIN: "__all__",
    SystemGroup.STATION_MANAGER: "__all__",
    SystemGroup.SUPERVISOR: {
        "stations.view_station",
        "stations.change_station",
        "inventory.view_fueltank",
        "inventory.view_tankdipreading",
        "sales.view_shift",
        "sales.view_fuelsale",
    },
    SystemGroup.PUMP_ATTENDANT: {
        "sales.add_fuelsale",
        "sales.change_fuelsale",
        "sales.view_fuelsale",
        "sales.view_shift",
    },
    SystemGroup.ACCOUNTANT: {
        "finance.view_invoice",
        "finance.add_payment",
        "finance.view_payment",
        "finance.view_receipt",
        "sales.view_fuelsale",
        "sales.view_shift",
    },
    SystemGroup.CUSTOMER: {
        "finance.view_invoice",
    },
}


def user_group_names(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    if getattr(user, "is_superuser", False):
        return {SystemGroup.ADMIN}
    cached_group_names = getattr(user, "_cached_group_names", None)
    if cached_group_names is not None:
        return cached_group_names
    if hasattr(user, "_prefetched_objects_cache") and "groups" in user._prefetched_objects_cache:
        group_names = {group.name for group in user._prefetched_objects_cache["groups"]}
    else:
        group_names = set(user.groups.values_list("name", flat=True))
    user._cached_group_names = group_names
    return group_names


def user_has_role(user, *roles):
    group_names = user_group_names(user)
    return any(role in group_names for role in roles)


def user_has_perm_or_role(user, permission_codename=None, *roles):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if permission_codename and user.has_perm(permission_codename):
        return True
    return user_has_role(user, *roles)


def can_access_settings(user):
    return user_has_role(user, SystemGroup.ADMIN)


def can_access_reports(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.ACCOUNTANT,
    )


def can_access_operations(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.PUMP_ATTENDANT,
    )


def can_manage_operations(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
    )


def can_access_fuel(user):
    return can_access_operations(user)


def can_manage_fuel(user):
    return can_manage_operations(user)


def can_approve_operations(user):
    return user_has_role(user, SystemGroup.ADMIN, SystemGroup.STATION_MANAGER)


def can_approve_fuel(user):
    return can_approve_operations(user)


def can_access_finance(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.ACCOUNTANT,
    )


def can_manage_finance(user):
    return user_has_role(user, SystemGroup.ADMIN, SystemGroup.ACCOUNTANT)


def can_create_orders(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
        SystemGroup.CUSTOMER,
    )


def can_edit_orders(user):
    return user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.STATION_MANAGER,
        SystemGroup.SUPERVISOR,
    )


def customer_profile_for(user):
    try:
        return getattr(user, "customer_profile", None)
    except Exception:
        return None


def restrict_queryset_for_user(queryset, user, customer_lookup):
    if getattr(user, "is_superuser", False):
        return queryset
    if user_has_role(user, SystemGroup.CUSTOMER):
        customer = customer_profile_for(user)
        if customer is None:
            return queryset.none()
        return queryset.filter(**{customer_lookup: customer})
    return queryset


def roles_required(*roles, permission=None):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not user_has_perm_or_role(request.user, permission, *roles):
                raise PermissionDenied("You do not have permission to access this resource.")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def ensure_rbac_groups():
    all_permissions = Permission.objects.all()
    for group_name, permission_codenames in GROUP_PERMISSION_MAP.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        if permission_codenames == "__all__":
            group.permissions.set(all_permissions)
            continue
        permissions = Permission.objects.filter(
            content_type__app_label__in=[codename.split(".", 1)[0] for codename in permission_codenames],
            codename__in=[codename.split(".", 1)[1] for codename in permission_codenames],
        )
        group.permissions.set(permissions)


def current_system_role(user):
    cached_role = getattr(user, "_cached_system_role", None)
    if cached_role is not None:
        return cached_role
    if getattr(user, "is_superuser", False):
        user._cached_system_role = SystemGroup.ADMIN
        return user._cached_system_role
    for internal, display in SYSTEM_ROLE_CHOICES:
        if user_has_role(user, display):
            user._cached_system_role = internal
            return user._cached_system_role
    role_value = getattr(user, "role", None)
    fallback_map = {
        "admin": "admin",
        "station_manager": "station_manager",
        "supervisor": "supervisor",
        "pump_attendant": "pump_attendant",
        "accountant": "accountant",
        "client": "client",
    }
    user._cached_system_role = fallback_map.get(role_value, SystemGroup.ADMIN)
    return user._cached_system_role


def legacy_request_role_for(user):
    system_role = current_system_role(user)
    compatibility_map = {
        SystemGroup.ADMIN: "admin",
        SystemGroup.STATION_MANAGER: "station_manager",
        SystemGroup.SUPERVISOR: "supervisor",
        SystemGroup.PUMP_ATTENDANT: "pump_attendant",
        SystemGroup.ACCOUNTANT: "accountant",
        SystemGroup.CUSTOMER: "client",
    }
    return compatibility_map[system_role]


def sync_user_to_system_role(user, system_role):
    from .models import User

    legacy_role_map = {
        "superadmin": User.Role.SUPERADMIN,
        "admin": User.Role.ADMIN,
        "station_manager": User.Role.STATION_MANAGER,
        "supervisor": User.Role.SUPERVISOR,
        "pump_attendant": User.Role.PUMP_ATTENDANT,
        "accountant": User.Role.ACCOUNTANT,
        "client": User.Role.CLIENT,
    }
    user.role = legacy_role_map.get(system_role, User.Role.ADMIN)
    user._selected_system_role = system_role
    if user._state.adding or user._state.db is None:
        return user

    ensure_rbac_groups()
    role_groups = list(Group.objects.filter(name__in=SystemGroup.ROLE_GROUPS))
    if role_groups:
        user.groups.remove(*role_groups)
    group = Group.objects.get(name=SYSTEM_ROLE_MAP.get(system_role, system_role))
    user.groups.add(group)
    user._cached_group_names = {system_role}
    user._cached_system_role = system_role
    return user


class RBACRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    allowed_roles = ()
    required_permission = None

    def test_func(self):
        return user_has_perm_or_role(self.request.user, self.required_permission, *self.allowed_roles)
