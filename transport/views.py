# Core Transport Module Views
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from accounts.decorators import driver_required
from transport.customers.forms import CustomerForm
from transport.customers.models import Customer
from transport.driver_ui_forms import DriverMessageForm, DriverProfileForm
from transport.drivers.forms import DriverForm
from transport.drivers.models import Driver
from transport.fuel.forms import FuelRequestForm
from transport.fuel.models import FuelDocument, FuelRequest
from transport.analytics.services import invalidate_notification_cache_for_user
from transport.messaging.models import DriverManagerMessage
from transport.routes.forms import RouteForm
from transport.routes.models import Route
from transport.trips.models import Trip
from transport.vehicles.forms import VehicleForm
from transport.vehicles.models import Vehicle

User = get_user_model()


DRIVER_PARTIALS = {
    "dashboard": "transport/driver/partials/dashboard.html",
    "trips": "transport/driver/partials/trips.html",
    "fuel": "transport/driver/partials/fuel.html",
    "messages": "transport/driver/partials/messages.html",
    "profile": "transport/driver/partials/profile.html",
}


def _support_staff_queryset():
    return User.objects.filter(role__in=["manager", "admin", "superadmin"], is_active=True).order_by("full_name")


def _driver_section_context(user, *, mark_messages_read=False, fuel_date_from="", fuel_date_to=""):
    driver = get_object_or_404(Driver, user=user)
    assigned_trips = (
        Trip.objects.filter(driver=driver, status=Trip.TripStatus.ASSIGNED)
        .select_related("route", "commodity_type", "customer", "vehicle")
        .order_by("-created_at")
    )
    active_trip = (
        Trip.objects.filter(driver=driver, status=Trip.TripStatus.IN_TRANSIT)
        .select_related("route", "commodity_type", "customer", "vehicle")
        .first()
    )
    completed_trips = (
        Trip.objects.filter(driver=driver, status=Trip.TripStatus.DELIVERED)
        .select_related("route", "customer")
        .order_by("-updated_at")[:5]
    )
    driver_trips = (
        Trip.objects.filter(driver=driver)
        .select_related("route", "commodity_type", "customer", "vehicle")
        .order_by("-created_at")[:20]
    )
    fuel_requests_qs = (
        FuelRequest.objects.filter(driver=user)
        .select_related("trip", "station")
        .prefetch_related("documents")
        .order_by("-created_at")
    )
    if fuel_date_from:
        fuel_requests_qs = fuel_requests_qs.filter(created_at__date__gte=fuel_date_from)
    if fuel_date_to:
        fuel_requests_qs = fuel_requests_qs.filter(created_at__date__lte=fuel_date_to)
    fuel_requests = fuel_requests_qs[:10]
    manager = _support_staff_queryset().first()
    conversation = DriverManagerMessage.objects.filter(driver=user).select_related("sender", "recipient").order_by("created_at")
    if mark_messages_read:
        conversation.filter(recipient=user, read_at__isnull=True).exclude(sender=user).update(read_at=timezone.now())

    return {
        "driver": driver,
        "assigned_trips": assigned_trips,
        "active_trip": active_trip,
        "completed_trips": completed_trips,
        "driver_trips": driver_trips,
        "total_trip_count": Trip.objects.filter(driver=driver).count(),
        "assigned_vehicle_plate": (
            active_trip.vehicle.plate_number
            if active_trip and active_trip.vehicle_id
            else (
                assigned_trips.exclude(vehicle__isnull=True).first().vehicle.plate_number
                if assigned_trips.exclude(vehicle__isnull=True).exists()
                else "No car"
            )
        ),
        "fuel_requests": fuel_requests,
        "assigned_count": assigned_trips.count(),
        "accepted_count": assigned_trips.filter(driver_response=Trip.DriverResponse.ACCEPTED).count(),
        "active_count": 1 if active_trip else 0,
        "completed_count": Trip.objects.filter(driver=driver, status=Trip.TripStatus.DELIVERED).count(),
        "fuel_request_count": FuelRequest.objects.filter(driver=user).count(),
        "fuel_filter_date_from": fuel_date_from,
        "fuel_filter_date_to": fuel_date_to,
        "message_count": conversation.count(),
        "manager_contact": manager,
        "support_contact": manager,
        "messages_thread": conversation,
        "message_form": DriverMessageForm(),
        "profile_form": DriverProfileForm(instance=user),
        "fuel_modal_form": FuelRequestForm(driver_user=user, trip=active_trip),
        "now": timezone.now(),
    }


def _driver_partial_response(request, tab, *, context=None, message_text=None, message_href=None):
    tab = tab if tab in DRIVER_PARTIALS else "dashboard"
    payload = context or _driver_section_context(request.user)
    response = render(request, DRIVER_PARTIALS[tab], payload)
    triggers = {
        "driver-set-tab": {"tab": tab},
    }
    if message_text:
        triggers["driver-toast"] = {"message": message_text, "href": message_href}
    response.headers["HX-Trigger"] = json.dumps(triggers)
    return response


@driver_required
def driver_shell(request, tab="dashboard"):
    tab_to_partial = {
        "dashboard": reverse("transport:driver_dashboard_partial"),
        "trips": reverse("transport:driver_trips_partial"),
        "fuel": reverse("transport:driver_fuel_partial"),
        "messages": reverse("transport:driver_messages_partial"),
        "profile": reverse("transport:driver_profile_partial"),
    }
    if tab not in tab_to_partial:
        tab = "dashboard"

    return render(
        request,
        "transport/driver_base.html",
        {
            "driver_spa": True,
            "initial_tab": tab,
            "initial_partial_url": tab_to_partial[tab],
        },
    )


@driver_required
def driver_dashboard(request):
    return driver_shell(request, tab="dashboard")


@driver_required
def driver_trips(request):
    return driver_shell(request, tab="trips")


@driver_required
def driver_fuel(request):
    return driver_shell(request, tab="fuel")


@driver_required
def driver_messages(request):
    return driver_shell(request, tab="messages")


@driver_required
def driver_profile(request):
    return driver_shell(request, tab="profile")


@driver_required
def driver_dashboard_partial(request):
    return _driver_partial_response(request, "dashboard")


@driver_required
def driver_trips_partial(request):
    return _driver_partial_response(request, "trips")


@driver_required
def driver_fuel_partial(request):
    context = _driver_section_context(
        request.user,
        fuel_date_from=request.GET.get("date_from", "").strip(),
        fuel_date_to=request.GET.get("date_to", "").strip(),
    )
    return _driver_partial_response(request, "fuel", context=context)


@driver_required
def driver_messages_partial(request):
    return _driver_partial_response(request, "messages", context=_driver_section_context(request.user, mark_messages_read=True))


@driver_required
def driver_messages_thread_partial(request):
    return render(
        request,
        "transport/driver/partials/_message_thread.html",
        _driver_section_context(request.user, mark_messages_read=True),
    )


@driver_required
def driver_profile_partial(request):
    return _driver_partial_response(request, "profile")


@driver_required
@require_POST
def driver_profile_update(request):
    context = _driver_section_context(request.user)
    form = DriverProfileForm(request.POST, request.FILES, instance=request.user)
    context["profile_form"] = form
    if not form.is_valid():
        return _driver_partial_response(request, "profile", context=context)

    user = form.save()
    driver = context["driver"]
    driver.name = user.full_name
    driver.phone = user.phone
    driver.email = user.email
    driver.save(update_fields=["name", "phone", "email", "updated_at"])
    return _driver_partial_response(
        request,
        "profile",
        context=_driver_section_context(request.user),
        message_text="Profile updated successfully.",
    )


@driver_required
@require_POST
def driver_message_send(request):
    context = _driver_section_context(request.user, mark_messages_read=True)
    manager = context["manager_contact"]
    form = DriverMessageForm(request.POST)
    context["message_form"] = form
    if manager is None:
        return _driver_partial_response(
            request,
            "messages",
        context=context,
        message_text="No manager account is available yet.",
        )
    if not form.is_valid():
        return _driver_partial_response(request, "messages", context=context)

    DriverManagerMessage.objects.create(
        driver=request.user,
        sender=request.user,
        recipient=manager,
        body=form.cleaned_data["body"],
    )
    invalidate_notification_cache_for_user(request.user.pk)
    invalidate_notification_cache_for_user(manager.pk)
    return _driver_partial_response(
        request,
        "messages",
        context=_driver_section_context(request.user, mark_messages_read=True),
        message_text="Message sent to your manager.",
    )


@driver_required
@require_POST
def driver_fuel_request_modal(request):
    context = _driver_section_context(request.user)
    active_trip = context["active_trip"]
    return_tab = request.POST.get("return_tab", "fuel")
    form = FuelRequestForm(request.POST, request.FILES, driver_user=request.user, trip=active_trip)
    context["fuel_modal_form"] = form
    if not form.is_valid():
        return _driver_partial_response(request, return_tab, context=context)

    fuel_request = form.save(commit=False)
    fuel_request.driver = request.user
    fuel_request.trip = form.cleaned_data["trip"]
    fuel_request.save()
    receipt = form.cleaned_data.get("receipt")
    if receipt:
        FuelDocument.objects.create(fuel_request=fuel_request, document=receipt)

    return _driver_partial_response(
        request,
        return_tab,
        context=_driver_section_context(request.user),
        message_text="Fuel request submitted.",
    )


@driver_required
def driver_assignment_state(request):
    driver = get_object_or_404(Driver, user=request.user)
    assigned_qs = Trip.objects.filter(driver=driver, status=Trip.TripStatus.ASSIGNED).order_by("-created_at")
    latest_trip = assigned_qs.first()
    unread_messages_qs = (
        DriverManagerMessage.objects.filter(driver=request.user, recipient=request.user, read_at__isnull=True)
        .exclude(sender=request.user)
        .select_related("sender")
        .order_by("-created_at")
    )
    latest_message = unread_messages_qs.first()
    fuel_cutoff = timezone.now() - timedelta(days=2)
    approved_fuel_qs = FuelRequest.objects.filter(
        driver=request.user,
        is_approved=True,
        approved_at__isnull=False,
        approved_at__gte=fuel_cutoff,
    )
    latest_fuel_approval = (
        approved_fuel_qs
        .select_related("trip", "station")
        .order_by("-approved_at")
        .first()
    )
    notifications = []
    if latest_trip:
        notifications.append(
            {
                "id": f"trip-{latest_trip.pk}",
                "kind": "trip",
                "title": "New trip assignment",
                "body": latest_trip.order_number,
                "href": reverse("transport:driver_trips"),
                "timestamp": latest_trip.created_at.isoformat(),
            }
        )
    if latest_message:
        notifications.append(
            {
                "id": f"message-{latest_message.pk}",
                "kind": "message",
                "title": f"New message from {latest_message.sender.full_name or latest_message.sender.email}",
                "body": latest_message.body[:80],
                "href": reverse("transport:driver_messages"),
                "timestamp": latest_message.created_at.isoformat(),
            }
        )
    if latest_fuel_approval:
        notifications.append(
            {
                "id": f"fuel-{latest_fuel_approval.pk}",
                "kind": "fuel",
                "title": "Fuel request approved",
                "body": latest_fuel_approval.trip.order_number if latest_fuel_approval.trip_id else "Fuel request approved",
                "href": reverse("transport:driver_fuel"),
                "timestamp": latest_fuel_approval.approved_at.isoformat(),
            }
        )
    notifications.sort(key=lambda item: item["timestamp"], reverse=True)
    return JsonResponse(
        {
            "assigned_count": assigned_qs.count(),
            "latest_assigned_trip_id": latest_trip.pk if latest_trip else None,
            "latest_assigned_order": latest_trip.order_number if latest_trip else "",
            "unread_message_count": unread_messages_qs.count(),
            "latest_message_id": latest_message.pk if latest_message else None,
            "latest_message_preview": latest_message.body[:80] if latest_message else "",
            "latest_message_sender": latest_message.sender.full_name if latest_message else "",
            "approved_fuel_count": approved_fuel_qs.count(),
            "latest_approved_fuel_id": latest_fuel_approval.pk if latest_fuel_approval else None,
            "latest_approved_fuel_trip": latest_fuel_approval.trip.order_number if latest_fuel_approval and latest_fuel_approval.trip_id else "",
            "notification_count": assigned_qs.count() + unread_messages_qs.count() + approved_fuel_qs.count(),
            "notifications": notifications[:6],
        }
    )


def driver_manifest(request):
    manifest = {
        "name": "ZALA Terminal Driver Workspace",
        "short_name": "ZALA/ECO Driver",
        "description": "Driver mobile workspace for trips, fuel, chat, and profile updates.",
        "start_url": "/transport/driver/",
        "scope": "/transport/driver/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#0b1f17",
        "theme_color": "#0f5c3d",
        "icons": [
            {
                "src": static("img/Afrilott.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": static("img/Afrilott.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "categories": ["business", "productivity", "travel"],
    }
    return HttpResponse(json.dumps(manifest), content_type="application/manifest+json")


def driver_service_worker(_request):
    script = """
const CACHE_NAME = "zalaeco-driver-v1";
const APP_SHELL = [
  "/transport/driver/",
  "/transport/driver/dashboard/",
  "/transport/driver/partials/dashboard/"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => null)
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy)).catch(() => null);
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;
        return caches.match("/transport/driver/partials/dashboard/");
      })
  );
});
"""
    return HttpResponse(script, content_type="application/javascript")


@login_required
def driver_dashboard_legacy(request):
    driver = get_object_or_404(Driver, user=request.user)
    
    assigned_trips = Trip.objects.filter(driver=driver, status=Trip.TripStatus.ASSIGNED).order_by('-created_at')
    active_trip = Trip.objects.filter(driver=driver, status=Trip.TripStatus.IN_TRANSIT).first()
    completed_trips = Trip.objects.filter(driver=driver, status=Trip.TripStatus.DELIVERED).order_by('-updated_at')[:5]
    fuel_requests = FuelRequest.objects.filter(driver=request.user).order_by('-created_at')[:5]

    context = {
        'assigned_trips': assigned_trips,
        'active_trip': active_trip,
        'completed_trips': completed_trips,
        'fuel_requests': fuel_requests,
    }
    return render(request, 'transport/driver_dashboard.html', context)

class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff access level"""
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in ['superadmin', 'admin', 'manager']

# ============ VEHICLE MANAGEMENT ============

class VehicleListView(StaffRequiredMixin, ListView):
    model = Vehicle
    template_name = 'transport/vehicles/list.html'
    context_object_name = 'vehicles'
    paginate_by = 20

    def get_queryset(self):
        queryset = Vehicle.objects.all()
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(plate_number__icontains=search) | 
                Q(model__icontains=search) | 
                Q(make__icontains=search)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')

class VehicleDetailView(StaffRequiredMixin, DetailView):
    model = Vehicle
    template_name = 'transport/vehicles/detail.html'
    context_object_name = 'vehicle'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vehicle = self.get_object()
        context['recent_trips'] = Trip.objects.filter(vehicle=vehicle).order_by('-created_at')[:5]
        context['maintenance_alerts'] = []  # TODO: Add maintenance logic
        return context

class VehicleCreateView(StaffRequiredMixin, CreateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'transport/vehicles/create.html'
    success_url = reverse_lazy('transport:vehicles-list')

    def form_valid(self, form):
        messages.success(self.request, f'Vehicle {form.instance.plate_number} created successfully!')
        return super().form_valid(form)

class VehicleUpdateView(StaffRequiredMixin, UpdateView):
    model = Vehicle
    form_class = VehicleForm
    template_name = 'transport/vehicles/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('transport:vehicle-detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f'Vehicle {form.instance.plate_number} updated successfully!')
        return super().form_valid(form)

# ============ DRIVER MANAGEMENT ============

class DriverListView(StaffRequiredMixin, ListView):
    model = Driver
    template_name = 'transport/drivers/list.html'
    context_object_name = 'drivers'
    paginate_by = 20

    def get_queryset(self):
        queryset = Driver.objects.select_related('user').all()
        search = self.request.GET.get('search')
        status = self.request.GET.get('status')
        
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(license_number__icontains=search)
            )
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')

class DriverDetailView(StaffRequiredMixin, DetailView):
    model = Driver
    template_name = 'transport/drivers/detail.html'
    context_object_name = 'driver'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        driver = self.get_object()
        context['recent_trips'] = Trip.objects.filter(driver=driver).order_by('-created_at')[:5]
        context['performance_metrics'] = {
            'total_trips': Trip.objects.filter(driver=driver, status='completed').count(),
            'total_distance': 0,  # TODO: Calculate from completed trips
            'avg_rating': 0,  # TODO: Calculate rating
        }
        return context

class DriverCreateView(StaffRequiredMixin, CreateView):
    model = Driver
    form_class = DriverForm
    template_name = 'transport/drivers/create.html'
    success_url = reverse_lazy('transport:drivers-list')

    def form_valid(self, form):
        messages.success(self.request, f'Driver {form.instance.user.get_full_name()} created successfully!')
        return super().form_valid(form)

class DriverUpdateView(StaffRequiredMixin, UpdateView):
    model = Driver
    form_class = DriverForm
    template_name = 'transport/drivers/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('transport:driver-detail', kwargs={'pk': self.object.pk})

# ============ CUSTOMER MANAGEMENT ============

class CustomerListView(StaffRequiredMixin, ListView):
    model = Customer
    template_name = 'transport/customers/list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        queryset = Customer.objects.all()
        search = self.request.GET.get('search')
        
        if search:
            queryset = queryset.filter(
                Q(company_name__icontains=search) |
                Q(contact_person__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset.order_by('-created_at')

class CustomerDetailView(StaffRequiredMixin, DetailView):
    model = Customer
    template_name = 'transport/customers/detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        context['recent_trips'] = Trip.objects.filter(customer=customer).order_by('-created_at')[:5]
        context['payment_summary'] = {
            'total_trips': Trip.objects.filter(customer=customer).count(),
            'total_revenue': 0,  # TODO: Calculate from completed trips
            'outstanding_balance': 0,  # TODO: Calculate outstanding payments
        }
        return context

class CustomerCreateView(StaffRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'transport/customers/create.html'
    success_url = reverse_lazy('transport:customers-list')

    def form_valid(self, form):
        messages.success(self.request, f'Customer {form.instance.company_name} created successfully!')
        return super().form_valid(form)

class CustomerUpdateView(StaffRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'transport/customers/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('transport:customer-detail', kwargs={'pk': self.object.pk})

# ============ ROUTE MANAGEMENT ============

class RouteListView(StaffRequiredMixin, ListView):
    model = Route
    template_name = 'transport/routes/list.html'
    context_object_name = 'routes'
    paginate_by = 20

    def get_queryset(self):
        queryset = Route.objects.all()
        search = self.request.GET.get('search')
        
        if search:
            queryset = queryset.filter(
                Q(origin__icontains=search) |
                Q(destination__icontains=search)
            )
        
        return queryset.order_by('origin', 'destination')

class RouteDetailView(StaffRequiredMixin, DetailView):
    model = Route
    template_name = 'transport/routes/detail.html'
    context_object_name = 'route'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = self.get_object()
        context['recent_trips'] = Trip.objects.filter(route=route).order_by('-created_at')[:5]
        context['route_analytics'] = {
            'total_trips': Trip.objects.filter(route=route).count(),
            'avg_duration': 0,  # TODO: Calculate from trip data
            'profitability': 0,  # TODO: Calculate profit metrics
        }
        return context

class RouteCreateView(StaffRequiredMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = 'transport/routes/create.html'
    success_url = reverse_lazy('transport:routes-list')

    def form_valid(self, form):
        messages.success(self.request, f'Route {form.instance.origin} ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ {form.instance.destination} created successfully!')
        return super().form_valid(form)

class RouteUpdateView(StaffRequiredMixin, UpdateView):
    model = Route
    form_class = RouteForm
    template_name = 'transport/routes/edit.html'
    
    def get_success_url(self):
        return reverse_lazy('transport:route-detail', kwargs={'pk': self.object.pk})

# ============ TRIP MANAGEMENT ============

class TripListView(StaffRequiredMixin, ListView):
    model = Trip
    template_name = 'transport/trips/list.html'
    context_object_name = 'trips'
    paginate_by = 20

    def get_queryset(self):
        queryset = Trip.objects.select_related('vehicle', 'driver', 'customer', 'route').all()
        
        # Filtering
        status = self.request.GET.get('status')
        driver_id = self.request.GET.get('driver')
        vehicle_id = self.request.GET.get('vehicle')
        search = self.request.GET.get('search')
        
        if status:
            queryset = queryset.filter(status=status)
        if driver_id:
            queryset = queryset.filter(driver_id=driver_id)
        if vehicle_id:
            queryset = queryset.filter(vehicle_id=vehicle_id)
        if search:
            queryset = queryset.filter(
                Q(order_number__icontains=search) |
                Q(customer__company_name__icontains=search)
            )
        
        return queryset.order_by('-created_at')

class TripDetailView(StaffRequiredMixin, DetailView):
    model = Trip
    template_name = 'transport/trips/detail.html'
    context_object_name = 'trip'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip = self.get_object()
        
        # Add additional context for trip management
        context['can_start'] = trip.status == 'assigned'
        context['can_complete'] = trip.status == 'in_progress'
        context['can_cancel'] = trip.status in ['pending', 'assigned']
        
        return context

# ============ AJAX VIEWS FOR STATUS UPDATES ============

@login_required
def update_trip_status(request, trip_id):
    """AJAX view to update trip status"""
    if not request.user.role in ['superadmin', 'admin', 'manager', 'driver']:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    trip = get_object_or_404(Trip, id=trip_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Trip.STATUS_CHOICES):
        trip.status = new_status
        trip.save()
        
        return JsonResponse({
            'success': True, 
            'message': f'Trip status updated to {trip.get_status_display()}'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid status'})

@login_required  
def vehicle_quick_status(request, vehicle_id):
    """AJAX view to quickly update vehicle status"""
    if not request.user.role in ['superadmin', 'admin', 'manager']:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id)
    new_status = request.POST.get('status')
    
    if new_status in dict(Vehicle.STATUS_CHOICES):
        vehicle.status = new_status
        vehicle.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Vehicle status updated to {vehicle.get_status_display()}'
        })
    
    return JsonResponse({'success': False, 'error': 'Invalid status'})
