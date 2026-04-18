from django.urls import path

from .views import (
    StationCreateView,
    StationDeleteView,
    StationExportExcelView,
    StationExportPDFView,
    StationListView,
    StationUpdateView,
    PumpListView,
    PumpCreateView,
    PumpUpdateView,
    PumpDeleteView,
    NozzleCreateView,
    NozzleUpdateView,
    NozzleDeleteView,
    TanksForPumpView,
)

app_name = "stations"

urlpatterns = [
    path("", StationListView.as_view(), name="list"),
    path("create/", StationCreateView.as_view(), name="create"),
    path("<int:pk>/update/", StationUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", StationDeleteView.as_view(), name="delete"),
    path("export/pdf/", StationExportPDFView.as_view(), name="export-pdf"),
    path("export/excel/", StationExportExcelView.as_view(), name="export-excel"),
    path("pumps/", PumpListView.as_view(), name="pumps"),
    path("pumps/create/", PumpCreateView.as_view(), name="pumps-create"),
    path("pumps/<int:pk>/update/", PumpUpdateView.as_view(), name="pumps-update"),
    path("pumps/<int:pk>/delete/", PumpDeleteView.as_view(), name="pumps-delete"),
    path("nozzles/create/", NozzleCreateView.as_view(), name="nozzles-create"),
    path("nozzles/<int:pk>/update/", NozzleUpdateView.as_view(), name="nozzles-update"),
    path("nozzles/<int:pk>/delete/", NozzleDeleteView.as_view(), name="nozzles-delete"),
    path("api/pump-tanks/", TanksForPumpView.as_view(), name="pump-tanks"),
]
