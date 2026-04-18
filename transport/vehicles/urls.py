from django.urls import path
from . import views

app_name = 'vehicles'

# Vehicle management endpoints
urlpatterns = [
    path("", views.VehicleListView.as_view(), name="list"),
    path("export/pdf/", views.VehiclePdfExportView.as_view(), name="export-pdf"),
    path("export/excel/", views.VehicleExcelExportView.as_view(), name="export-excel"),
    path("owners/", views.VehicleOwnerListView.as_view(), name="owner-list"),
    path("owners/<int:pk>/", views.VehicleOwnerDetailView.as_view(), name="owner-detail"),
    path("create/", views.VehicleCreateView.as_view(), name="create"),
    path("<int:pk>/", views.VehicleDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.VehicleUpdateView.as_view(), name="edit"),
    path("<int:vehicle_id>/status/", views.vehicle_quick_status, name="status-update"),
    
    # Additional vehicle-specific routes  
    path("<int:pk>/history/", views.VehicleDetailView.as_view(), name="history"),
    path("<int:pk>/maintenance/", views.VehicleDetailView.as_view(), name="maintenance-history"),
    path("<int:pk>/fuel/", views.VehicleDetailView.as_view(), name="fuel-history"),
    path("<int:pk>/trips/", views.VehicleDetailView.as_view(), name="trip-history"),
]
