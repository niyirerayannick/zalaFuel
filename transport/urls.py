from django.urls import include, path

from transport.analytics.views import dashboard_view

from . import views

# Transport Management System URL Configuration
# Provides a clean API structure for all transport modules

app_name = "transport"

urlpatterns = [
    path("driver.webmanifest", views.driver_manifest, name="driver_manifest"),
    path("driver-sw.js", views.driver_service_worker, name="driver_service_worker"),
    path("driver/", views.driver_dashboard, name="driver_home"),
    path("driver/dashboard/", views.driver_dashboard, name="driver_dashboard"),
    path("driver/trips/", views.driver_trips, name="driver_trips"),
    path("driver/fuel/", views.driver_fuel, name="driver_fuel"),
    path("driver/messages/", views.driver_messages, name="driver_messages"),
    path("driver/profile/", views.driver_profile, name="driver_profile"),
    path("driver/partials/dashboard/", views.driver_dashboard_partial, name="driver_dashboard_partial"),
    path("driver/partials/trips/", views.driver_trips_partial, name="driver_trips_partial"),
    path("driver/partials/fuel/", views.driver_fuel_partial, name="driver_fuel_partial"),
    path("driver/partials/messages/", views.driver_messages_partial, name="driver_messages_partial"),
    path("driver/partials/messages/thread/", views.driver_messages_thread_partial, name="driver_messages_thread_partial"),
    path("driver/partials/profile/", views.driver_profile_partial, name="driver_profile_partial"),
    path("driver/profile/update/", views.driver_profile_update, name="driver_profile_update"),
    path("driver/messages/send/", views.driver_message_send, name="driver_message_send"),
    path("driver/fuel/request-modal/", views.driver_fuel_request_modal, name="driver_fuel_request_modal"),
    path("driver/assignment-state/", views.driver_assignment_state, name="driver_assignment_state"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("analytics/", include("transport.analytics.urls", namespace="analytics")),
    path("vehicles/", include("transport.vehicles.urls", namespace="vehicles")),
    path("drivers/", include("transport.drivers.urls", namespace="drivers")),
    path("customers/", include("transport.customers.urls", namespace="customers")),
    path("orders/", include("transport.orders.urls", namespace="orders")),
    path("routes/", include("transport.routes.urls", namespace="routes")),
    path("fuel/", include("transport.fuel.urls", namespace="fuel")),
    path("trips/", include("transport.trips.urls", namespace="trips")),
    path("maintenance/", include("transport.maintenance.urls", namespace="maintenance")),
    path("finance/", include("transport.finance.urls", namespace="finance")),
    path("reports/", include("transport.reports.urls", namespace="reports")),
    path("messaging/", include("transport.messaging.urls", namespace="messaging")),
]
