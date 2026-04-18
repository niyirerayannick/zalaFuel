from django.urls import path

from .views import (
    POSView,
    ShiftListView,
    ShiftDetailView,
    ShiftOpenView,
    ShiftCloseView,
    PumpChoicesView,
    NozzleChoicesView,
    NozzleTankInfoView,
    StationAttendantsView,
    StationNozzleReadingsView,
    CreateSaleView,
)

app_name = "sales"

urlpatterns = [
    path("pos/", POSView.as_view(), name="pos"),
    path("shifts/", ShiftListView.as_view(), name="shifts"),
    path("shifts/<int:pk>/", ShiftDetailView.as_view(), name="shifts-detail"),
    path("shifts/open/", ShiftOpenView.as_view(), name="shifts-open"),
    path("shifts/<int:pk>/close/", ShiftCloseView.as_view(), name="shifts-close"),
    path("api/pumps/", PumpChoicesView.as_view(), name="api-pumps"),
    path("api/nozzles/", NozzleChoicesView.as_view(), name="api-nozzles"),
    path("api/station-attendants/", StationAttendantsView.as_view(), name="api-station-attendants"),
    path("api/station-nozzle-readings/", StationNozzleReadingsView.as_view(), name="api-station-nozzle-readings"),
    path("api/nozzle/<int:nozzle_id>/tank/", NozzleTankInfoView.as_view(), name="api-nozzle-tank"),
    path("api/sales/", CreateSaleView.as_view(), name="api-sales-create"),
]
