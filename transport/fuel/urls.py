from django.urls import path
from . import views

app_name = 'fuel'

urlpatterns = [
    path("", views.fuel_dashboard, name="list"),
    path("export/pdf/", views.FuelPdfExportView.as_view(), name="export-pdf"),
    path("export/excel/", views.FuelExcelExportView.as_view(), name="export-excel"),
    path("analytics/", views.fuel_analytics, name="analytics"),
    path("<int:pk>/", views.FuelRequestDetailView.as_view(), name="detail"),
    path("<int:pk>/approve/", views.approve_fuel_request, name="approve"),
    path("request/", views.request_fuel, name="request"),
    path("request/<int:fuel_request_id>/upload/", views.upload_fuel_document, name="upload_document"),
]
