from django.urls import path

from .views import (
    OMCSalesDashboardView,
    OMCSalesEntryCreateView,
    OMCSalesEntryExcelExportView,
    OMCSalesEntryPdfExportView,
    OMCSalesEntryUpdateView,
)

app_name = "sales"

urlpatterns = [
    path("", OMCSalesDashboardView.as_view(), name="dashboard"),
    path("export/excel/", OMCSalesEntryExcelExportView.as_view(), name="export-excel"),
    path("export/pdf/", OMCSalesEntryPdfExportView.as_view(), name="export-pdf"),
    path("new/", OMCSalesEntryCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", OMCSalesEntryUpdateView.as_view(), name="update"),
]
