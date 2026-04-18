from django.urls import path

from .views import (
    client_support_view,
    dashboard_view, 
    dashboard_api,
    documentation_view,
    notifications_view,
    send_client_support_message,
    send_driver_message,
    support_view,
    VehicleListView,
    TripListView, 
    TripDetailView,
    driver_dashboard,
    client_dashboard,
    executive_dashboard_api  # Legacy endpoint
)

app_name = "analytics"

urlpatterns = [
    # Root analytics page (redirect to dashboard)
    path("", dashboard_view, name="overview"),
    
    # Main dashboards
    path("dashboard/", dashboard_view, name="dashboard"),
    path("documentation/", documentation_view, name="documentation"),
    path("notifications/", notifications_view, name="notifications"),
    path("api/dashboard/", dashboard_api, name="dashboard-api"),
    path("dashboard/driver-messages/send/", send_driver_message, name="driver-message-send"),
    path("support/", support_view, name="support"),
    path("client-dashboard/support/send/", send_client_support_message, name="client-support-send"),
    path("client-dashboard/support/", client_support_view, name="client-support"),
    path("driver-dashboard/", driver_dashboard, name="driver-dashboard"),
    path("client-dashboard/", client_dashboard, name="client-dashboard"),
    
    # Management views
    path("vehicles/", VehicleListView.as_view(), name="vehicles-list"),
    path("trips/", TripListView.as_view(), name="trips-list"),
    path("trips/<int:pk>/", TripDetailView.as_view(), name="trip-detail"),
    
    # Legacy API endpoint
    path("executive/", executive_dashboard_api, name="atms-executive-dashboard"),
]
