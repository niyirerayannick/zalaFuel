from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.cache import cache
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from transport.analytics.services import (
    executive_dashboard_metrics,
    full_dashboard_context,
    invalidate_notification_cache_for_user,
    normalize_range_key,
    user_notification_payload,
)
from transport.driver_ui_forms import DriverMessageForm
from transport.drivers.models import Driver
from transport.messaging.models import DriverManagerMessage
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle
from accounts.rbac import SystemGroup, user_has_role

User = get_user_model()


def _can_access_staff_support(user):
    return user.is_authenticated and user_has_role(
        user,
        SystemGroup.ADMIN,
        SystemGroup.OPERATIONS_MANAGER,
        SystemGroup.FINANCE,
    )


DOCUMENTATION_MODULES = [
    {
        "eyebrow": "Command Center",
        "title": "Dashboard & Analytics",
        "icon": "dashboard",
        "summary": "Track fleet health, operational KPIs, fuel activity, alerts, and performance trends from one place.",
        "highlights": [
            "Use KPI cards to jump into the matching full list for vehicles, trips, drivers, and alerts.",
            "Apply the dashboard range filter to refresh the metrics for the selected reporting period.",
            "Use the support area for direct messaging with any active system user.",
        ],
        "workflow": [
            "Open the dashboard to review live operational numbers.",
            "Click a KPI to inspect the detailed list behind that metric.",
            "Use support and reports when a metric needs action or escalation.",
        ],
    },
    {
        "eyebrow": "Fleet Control",
        "title": "Vehicles, Drivers & Routes",
        "icon": "local_shipping",
        "summary": "Manage transport resources before trips are created, including ownership, availability, route setup, and export registers.",
        "highlights": [
            "Vehicles track status, ownership, capacity, maintenance state, and export-ready registers.",
            "Drivers track assignment state, work status, license documents, and availability.",
            "Routes provide the origin, destination, and distance used across trips, fuel, and analytics.",
        ],
        "workflow": [
            "Register vehicles and external owners first.",
            "Create or update drivers and mark them as company or external drivers.",
            "Maintain route distance accurately so trip, fuel, and performance analytics stay correct.",
        ],
    },
    {
        "eyebrow": "Commercial Flow",
        "title": "Customers, Orders & Shipments",
        "icon": "inventory_2",
        "summary": "Capture customer demand, order quantity, cargo weight, and shipment readiness before dispatch.",
        "highlights": [
            "Orders keep business quantity and logistics weight separate for more accurate planning.",
            "Shipments only allow remaining weight to be prepared, which prevents over-shipping.",
            "Quantity, unit, and weight are validated so operations reflect real logistics behavior.",
        ],
        "workflow": [
            "Register the customer and create the order with quantity, unit, weight, and commercial price.",
            "Prepare shipments from orders that still have remaining weight to move.",
            "Assign prepared shipments to a trip when dispatch is ready.",
        ],
    },
    {
        "eyebrow": "Dispatch",
        "title": "Trips & Delivery Workflow",
        "icon": "route",
        "summary": "Trips connect routes, vehicles, drivers, and shipments into one operational job with approval, transit, and completion stages.",
        "highlights": [
            "Trips can be approved, rejected, started, delivered, and completed using the existing workflow rules.",
            "Trip pages show shipment weight, financial summary, invoices, reports, and linked expenses.",
            "Completing a trip releases the vehicle and driver back to available status automatically.",
        ],
        "workflow": [
            "Create a trip from available shipments and assign the route, vehicle, and driver.",
            "Approve or reject the trip based on readiness and operating requirements.",
            "Start, track, and complete the trip to finalize revenue, expenses, and resource availability.",
        ],
    },
    {
        "eyebrow": "Operations Costing",
        "title": "Fuel, Expenses & Maintenance",
        "icon": "local_gas_station",
        "summary": "Record operating costs, fuel usage, maintenance activity, and loss indicators without breaking the trip workflow.",
        "highlights": [
            "Fuel expenses support liters and unit price so the total amount is auto-calculated.",
            "Fuel dashboards and analytics show distance, cost per kilometer, vehicle efficiency, and high-consumption trips.",
            "Maintenance records track scheduled work, workshops, downtime, and repair cost history.",
        ],
        "workflow": [
            "Record trip expenses directly from the trip detail page or from finance expenses.",
            "Use fuel dashboards to spot inefficient trips and vehicle consumption trends.",
            "Track maintenance promptly to keep availability and service status accurate.",
        ],
    },
    {
        "eyebrow": "Financial Control",
        "title": "Payments, Invoices & Reports",
        "icon": "payments",
        "summary": "Turn completed transport activity into invoice-ready revenue, trip reports, and payment tracking in the system currency.",
        "highlights": [
            "Invoices pull payment instructions from system settings and support PDF verification workflows.",
            "Trip reports export to PDF and Excel and can be emailed to registered users.",
            "Financial summaries group rental fee, other expenses, revenue, and net profit per trip.",
        ],
        "workflow": [
            "Generate or refresh invoices when the trip or order is ready for billing.",
            "Record payments and manual revenue under finance using the system currency.",
            "Export PDF and Excel documents for trips, fuel, vehicles, drivers, and reports as needed.",
        ],
    },
    {
        "eyebrow": "Administration",
        "title": "Users, Roles & System Settings",
        "icon": "settings",
        "summary": "Control who can access which module, set company identity, and maintain shared finance and communication defaults.",
        "highlights": [
            "System settings store company details, default currency, exchange helpers, and bank payment information.",
            "Users and role management control access for admins, operations, finance, clients, and related teams.",
            "Activity logs and support tools help track actions and respond to operational questions quickly.",
        ],
        "workflow": [
            "Create users and assign the correct roles before onboarding them to operations.",
            "Keep company profile, currency, and banking details up to date in system settings.",
            "Review activity logs and support conversations when investigating issues or approvals.",
        ],
    },
]


def _support_staff_queryset():
    return User.objects.filter(role__in=["superadmin", "admin", "manager"], is_active=True).order_by("full_name")


def _staff_support_context(request, selected_user_id=""):
    all_users = list(
        User.objects.filter(is_active=True)
        .exclude(pk=request.user.pk)
        .annotate(
            last_message_at=Max(
                "driver_conversations__created_at",
                filter=Q(driver_conversations__sender=request.user) | Q(driver_conversations__recipient=request.user),
            )
        )
        .order_by("-last_message_at", "full_name", "email")
    )

    selected_user = None
    if selected_user_id:
        selected_user = next((user for user in all_users if str(user.id) == selected_user_id), None)

    conversation_users = [user for user in all_users if getattr(user, "last_message_at", None)]
    if selected_user and all(user.pk != selected_user.pk for user in conversation_users):
        conversation_users.insert(0, selected_user)
    if selected_user is None and conversation_users:
        selected_user = conversation_users[0]

    selected_messages = []
    if selected_user is not None:
        selected_messages = list(
            DriverManagerMessage.objects.filter(driver=selected_user)
            .select_related("driver", "sender", "recipient")
            .order_by("created_at")[:50]
        )
        for message in selected_messages:
            message.was_unread = (
                message.sender_id != request.user.id
                and message.recipient_id == request.user.id
                and message.read_at is None
            )
        DriverManagerMessage.objects.filter(
            driver=selected_user,
            recipient=request.user,
            read_at__isnull=True,
        ).exclude(sender=request.user).update(read_at=timezone.now())

    unread_counts = {
        row["driver"]: row["total"]
        for row in DriverManagerMessage.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        )
        .exclude(sender=request.user)
        .values("driver")
        .annotate(total=Count("id"))
    }

    message_form = DriverMessageForm()
    message_form.fields["body"].widget.attrs["placeholder"] = "Reply to user..."

    support_user_cards = []
    for user in conversation_users:
        support_user_cards.append(
            {
                "user": user,
                "role_label": getattr(user, "get_role_display", lambda: user.role.title())(),
                "contact": user.phone or user.email or "-",
                "unread_count": unread_counts.get(user.pk, 0),
                "has_conversation": bool(getattr(user, "last_message_at", None)),
            }
        )

    support_available_users = []
    for user in all_users:
        support_available_users.append(
            {
                "user": user,
                "role_label": getattr(user, "get_role_display", lambda: user.role.title())(),
                "contact": user.phone or user.email or "-",
                "has_conversation": bool(getattr(user, "last_message_at", None)),
            }
        )

    return {
        "support_conversation_users": conversation_users,
        "support_user_cards": support_user_cards,
        "support_available_users": support_available_users,
        "selected_support_user": selected_user,
        "support_messages": selected_messages,
        "support_message_form": message_form,
        "support_message_total": DriverManagerMessage.objects.count(),
        "support_user_total": len(conversation_users),
        "support_available_total": len(all_users),
        "support_message_unread": DriverManagerMessage.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).exclude(sender=request.user).count(),
    }


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Ensures user is staff (admin, manager, or superadmin)."""

    def test_func(self):
        return _can_access_staff_support(self.request.user)


@login_required
def dashboard_view(request):
    """Main ZALA Terminal dashboard showing key metrics and recent activity."""
    if request.user.role not in ["superadmin", "admin", "manager"]:
        return render(request, "transport/access_denied.html")

    partial = request.GET.get("partial")
    range_key = normalize_range_key(request.GET.get("range", "month"))
    use_cache = partial != "content"
    cache_key = f"dashboard_context_{request.user.role}_{range_key}"
    context = None

    if use_cache:
        try:
            context = cache.get(cache_key)
        except Exception:
            context = None

    if not context:
        context = full_dashboard_context(range_key)
        if use_cache:
            try:
                cache.set(cache_key, context, 300)
            except Exception:
                pass

    context["page_title"] = "Dashboard"
    context["page_subtitle"] = "Fleet operations, analytics, and quick actions"
    context["current_range"] = range_key

    if partial == "content":
        return render(request, "transport/_dashboard_content.html", context)

    return render(request, "transport/dashboard.html", context)


@login_required
@require_POST
def send_driver_message(request):
    if not _can_access_staff_support(request.user):
        return render(request, "transport/access_denied.html")

    driver_id = (request.POST.get("driver_id") or request.POST.get("user_id") or "").strip()
    body = request.POST.get("body", "").strip()
    range_key = normalize_range_key(request.POST.get("range", "month"))

    driver_user = get_object_or_404(User.objects.filter(is_active=True).exclude(pk=request.user.pk), pk=driver_id)
    form = DriverMessageForm({"body": body})
    if form.is_valid():
        DriverManagerMessage.objects.create(
            driver=driver_user,
            sender=request.user,
            recipient=driver_user,
            body=form.cleaned_data["body"],
        )
        invalidate_notification_cache_for_user(driver_user.pk)
        invalidate_notification_cache_for_user(request.user.pk)
        messages.success(request, f"Message sent to {driver_user.full_name}.")
    else:
        messages.error(request, form.errors.get("body", ["Unable to send message."])[0])

    support_url = f"/transport/analytics/support/?range={range_key}&user={driver_user.pk}"
    return redirect(support_url)


@login_required
def support_view(request):
    if not _can_access_staff_support(request.user):
        return render(request, "transport/access_denied.html")

    selected_user_id = request.GET.get("user", "").strip()
    context = {
        "page_title": "Support",
        "page_subtitle": "Reply to support conversations from drivers and clients",
        "current_range": normalize_range_key(request.GET.get("range", "month")),
    }
    context.update(_staff_support_context(request, selected_user_id))
    return render(request, "transport/support_staff.html", context)


@login_required
def dashboard_api(request):
    """API endpoint for dashboard metrics (for AJAX updates)."""
    if request.user.role not in ["superadmin", "admin", "manager"]:
        return JsonResponse({"error": "Access denied"}, status=403)

    range_key = normalize_range_key(request.GET.get("range", "month"))
    metrics = executive_dashboard_metrics(range_key)
    for key, value in metrics.items():
        if hasattr(value, "quantize"):
            metrics[key] = str(value)

    return JsonResponse(metrics)


@login_required
def documentation_view(request):
    context = {
        "page_title": "System Documentation",
        "page_subtitle": "Understand how each ZALA Terminal module works, what data it manages, and how the workflows connect.",
        "current_range": normalize_range_key(request.GET.get("range", "month")),
        "documentation_modules": DOCUMENTATION_MODULES,
        "documentation_quick_links": [
            {"label": "Dashboard", "url": "/transport/analytics/dashboard/", "icon": "dashboard"},
            {"label": "Vehicles", "url": "/transport/vehicles/", "icon": "local_shipping"},
            {"label": "Orders", "url": "/transport/orders/", "icon": "inventory_2"},
            {"label": "Trips", "url": "/transport/trips/", "icon": "route"},
            {"label": "Fuel", "url": "/transport/fuel/", "icon": "local_gas_station"},
            {"label": "Finance", "url": "/transport/finance/", "icon": "payments"},
        ],
        "documentation_flow": [
            "Set up vehicles, drivers, routes, and customers.",
            "Create orders with business quantity, unit, and logistics weight.",
            "Prepare shipments from remaining order weight and assign them to trips.",
            "Approve, start, deliver, and complete trips.",
            "Record fuel, expenses, maintenance, invoices, and payments for full operational visibility.",
        ],
    }
    return render(request, "transport/documentation.html", context)


@login_required
def notifications_view(request):
    context = {
        "page_title": "Notifications",
        "page_subtitle": "Review alerts, expiring records, and unread support messages in one place.",
    }
    context.update(user_notification_payload(request.user, limit=50))
    return render(request, "transport/notifications.html", context)


class VehicleListView(StaffRequiredMixin, ListView):
    """List all vehicles with filtering and search."""

    model = Vehicle
    template_name = "transport/vehicles/list.html"
    context_object_name = "vehicles"
    paginate_by = 20

    def get_queryset(self):
        queryset = Vehicle.objects.all()

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(plate_number__icontains=search)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("plate_number")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Fleet Management"
        context["status_choices"] = Vehicle.VehicleStatus.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("search", "")
        return context


class TripListView(ListView):
    """List trips based on user role."""

    model = Trip
    template_name = "transport/trips/list.html"
    context_object_name = "trips"
    paginate_by = 20

    def get_queryset(self):
        user = self.request.user
        queryset = Trip.objects.select_related("customer", "vehicle", "driver", "route")

        if user.role == "driver":
            try:
                driver = Driver.objects.get(user=user)
                queryset = queryset.filter(driver=driver)
            except Driver.DoesNotExist:
                queryset = queryset.none()
        elif user.role == "client":
            try:
                queryset = queryset.filter(customer__user=user)
            except Exception:
                queryset = queryset.none()

        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(order_number__icontains=search)

        status = self.request.GET.get("status")
        if status:
            queryset = queryset.filter(status=status)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Trips Management"
        context["status_choices"] = Trip.TripStatus.choices
        context["selected_status"] = self.request.GET.get("status", "")
        context["search_query"] = self.request.GET.get("search", "")
        return context


class TripDetailView(DetailView):
    """Detailed view of a trip."""

    model = Trip
    template_name = "transport/trips/detail.html"
    context_object_name = "trip"

    def get_queryset(self):
        user = self.request.user
        queryset = Trip.objects.select_related("customer", "vehicle", "driver", "route")

        if user.role == "driver":
            try:
                driver = Driver.objects.get(user=user)
                queryset = queryset.filter(driver=driver)
            except Driver.DoesNotExist:
                queryset = queryset.none()
        elif user.role == "client":
            try:
                queryset = queryset.filter(customer__user=user)
            except Exception:
                queryset = queryset.none()

        return queryset


@login_required
def driver_dashboard(request):
    """Dashboard specifically for drivers."""
    if request.user.role != "driver":
        return render(request, "transport/access_denied.html")

    try:
        driver = Driver.objects.get(user=request.user)
        active_trips = Trip.objects.filter(
            driver=driver,
            status__in=[Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT],
        ).select_related("customer", "route")

        recent_trips = Trip.objects.filter(driver=driver).order_by("-created_at")[:10]

        context = {
            "driver": driver,
            "active_trips": active_trips,
            "recent_trips": recent_trips,
            "page_title": "Driver Dashboard",
        }

        return render(request, "transport/driver_dashboard.html", context)

    except Driver.DoesNotExist:
        return render(
            request,
            "transport/access_denied.html",
            {"message": "Driver profile not found. Please contact administrator."},
        )


@login_required
def client_dashboard(request):
    """Dashboard for clients/customers."""
    if request.user.role != "client":
        return render(request, "transport/access_denied.html")

    trip_queryset = Trip.objects.filter(customer__user=request.user).select_related(
        "customer", "vehicle", "route"
    ).order_by("-created_at")

    customer_trips = trip_queryset[:20]

    active_orders = trip_queryset.filter(
        status__in=[Trip.TripStatus.APPROVED, Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT]
    )[:10]

    context = {
        "customer_trips": customer_trips,
        "active_orders": active_orders,
        "page_title": "My Orders",
    }

    return render(request, "transport/client_dashboard.html", context)


@login_required
def client_support_view(request):
    if request.user.role != "client":
        return render(request, "transport/access_denied.html")

    support_contact = _support_staff_queryset().first()
    support_messages = DriverManagerMessage.objects.filter(driver=request.user).select_related("sender", "recipient")
    support_messages.filter(recipient=request.user, read_at__isnull=True).exclude(sender=request.user).update(read_at=timezone.now())
    support_form = DriverMessageForm()
    support_form.fields["body"].widget.attrs["placeholder"] = "Ask support about your orders..."

    return render(
        request,
        "transport/support_client.html",
        {
            "page_title": "Support",
            "page_subtitle": "Chat with operations support",
            "support_contact": support_contact,
            "support_messages": support_messages[:50],
            "support_message_form": support_form,
        },
    )


@login_required
@require_POST
def send_client_support_message(request):
    if request.user.role != "client":
        return render(request, "transport/access_denied.html")

    support_contact = _support_staff_queryset().first()
    form = DriverMessageForm(request.POST)
    if support_contact is None:
        messages.error(request, "Support is not available yet.")
        return redirect("transport:analytics:client-support")

    if form.is_valid():
        DriverManagerMessage.objects.create(
            driver=request.user,
            sender=request.user,
            recipient=support_contact,
            body=form.cleaned_data["body"],
        )
        invalidate_notification_cache_for_user(request.user.pk)
        invalidate_notification_cache_for_user(support_contact.pk)
        messages.success(request, "Message sent to support.")
    else:
        messages.error(request, form.errors.get("body", ["Unable to send message."])[0])

    return redirect("transport:analytics:client-support")


def executive_dashboard_api(_request):
    """Legacy API endpoint for compatibility."""
    return JsonResponse(executive_dashboard_metrics())
