from django.urls import path

from .views import (
    ReportsDashboardView,
    ExportExcelView,
    GenerateSOAReportView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportsDashboardView.as_view(), name="dashboard"),
    path("soa/export/", GenerateSOAReportView.as_view(), name="soa-export"),
    path("export/excel/", ExportExcelView.as_view(), name="export-excel"),
]
