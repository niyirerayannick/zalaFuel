from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from .models import User
from .rbac import (
    SystemGroup,
    can_access_finance,
    can_access_operations,
    can_access_reports,
    can_access_settings,
    can_approve_operations,
    can_create_orders,
    can_edit_orders,
    can_manage_finance,
    can_manage_operations,
    can_access_fuel,
    can_manage_fuel,
    can_approve_fuel,
    current_system_role,
    legacy_request_role_for,
    user_group_names,
    user_has_role,
)


class RBACMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            session_authenticated_at = request.session.get("session_authenticated_at")
            session_authenticated_at_dt = parse_datetime(session_authenticated_at) if session_authenticated_at else None
            if user.session_invalid_before and (
                session_authenticated_at_dt is None or session_authenticated_at_dt <= user.session_invalid_before
            ):
                logout(request)
                messages.error(request, "Your session was secured. Please sign in again.")
                return redirect("accounts:login")

            exempt_paths = {
                reverse("accounts:logout"),
                reverse("accounts:password-change-required"),
            }
            if getattr(user, "must_change_password", False) and request.path not in exempt_paths:
                return redirect("accounts:password-change-required")

            legacy_role = user.role
            request.rbac_groups = user_group_names(user)
            request.current_system_role = current_system_role(user)
            request.is_admin_role = user_has_role(user, SystemGroup.ADMIN)
            request.is_station_manager = user_has_role(user, SystemGroup.STATION_MANAGER)
            request.is_supervisor = user_has_role(user, SystemGroup.SUPERVISOR)
            request.is_pump_attendant = user_has_role(user, SystemGroup.PUMP_ATTENDANT)
            request.is_finance_role = user_has_role(user, SystemGroup.ACCOUNTANT)
            request.is_customer_role = user_has_role(user, SystemGroup.CUSTOMER)
            request.is_operations_role = any(
                (request.is_admin_role, request.is_station_manager, request.is_supervisor, request.is_pump_attendant)
            )
            request.is_staff_role = any(
                (
                    request.is_admin_role,
                    request.is_station_manager,
                    request.is_supervisor,
                    request.is_pump_attendant,
                    request.is_finance_role,
                )
            )
            request.can_access_settings = can_access_settings(user)
            request.can_access_reports = can_access_reports(user)
            request.can_access_operations = can_access_operations(user)
            request.can_manage_operations = can_manage_operations(user)
            request.can_approve_operations = can_approve_operations(user)
            request.can_access_fuel = can_access_fuel(user)
            request.can_manage_fuel = can_manage_fuel(user)
            request.can_approve_fuel = can_approve_fuel(user)
            request.can_access_finance = can_access_finance(user)
            request.can_manage_finance = can_manage_finance(user)
            request.can_create_orders = can_create_orders(user)
            request.can_edit_orders = can_edit_orders(user)

            if legacy_role == "driver":
                logout(request)
                messages.error(request, "Driver accounts are no longer allowed to sign in.")
                return redirect("accounts:login")

            # Preserve legacy view/template checks without granting finance or customers
            # the wrong internal modules. Groups remain the source of truth.
            user.role = legacy_request_role_for(user)

        return self.get_response(request)
