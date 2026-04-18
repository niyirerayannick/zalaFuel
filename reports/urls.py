from django.urls import path

from .views import (
    FinancialReportView,
    InventoryReportView,
    ReportsDashboardView,
    SalesReportView,
    ShiftReportView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportsDashboardView.as_view(), name="dashboard"),
    path("sales/", SalesReportView.as_view(), name="sales"),
    path("inventory/", InventoryReportView.as_view(), name="inventory"),
    path("shifts/", ShiftReportView.as_view(), name="shifts"),
    path("financial/", FinancialReportView.as_view(), name="financial"),
]
