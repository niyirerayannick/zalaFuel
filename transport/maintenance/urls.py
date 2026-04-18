from django.urls import path
from . import views

app_name = 'maintenance'

# Maintenance management endpoints
urlpatterns = [
    path("", views.MaintenanceListView.as_view(), name="list"),
    path("export/pdf/", views.MaintenancePdfExportView.as_view(), name="export-pdf"),
    path("export/excel/", views.MaintenanceExcelExportView.as_view(), name="export-excel"),
    path("service-types/", views.service_types_api, name="service-types"),
    path("create/", views.MaintenanceCreateView.as_view(), name="create"),
    path("<int:pk>/approve/", views.approve_maintenance_request, name="approve"),
    path("<int:pk>/", views.MaintenanceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.MaintenanceUpdateView.as_view(), name="edit"),
]
