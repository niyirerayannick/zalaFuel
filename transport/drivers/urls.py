from django.urls import path
from . import views

app_name = 'drivers'

# Driver management endpoints
urlpatterns = [
    path("", views.DriverListView.as_view(), name="list"),
    path("export/pdf/", views.DriverPdfExportView.as_view(), name="export-pdf"),
    path("export/excel/", views.DriverExcelExportView.as_view(), name="export-excel"),
    path("create/", views.DriverCreateView.as_view(), name="create"),
    path("<int:pk>/", views.DriverDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.DriverUpdateView.as_view(), name="edit"),
    path("<int:driver_id>/status/", views.driver_quick_status, name="status-update"),
    
    # Driver-specific routes
    path("<int:pk>/trips/", views.DriverDetailView.as_view(), name="trip-history"),
    path("<int:pk>/performance/", views.DriverDetailView.as_view(), name="performance"),
    path("<int:pk>/documents/", views.DriverDetailView.as_view(), name="documents"),
    path("license-alerts/", views.DriverListView.as_view(), name="license-alerts"),
]
