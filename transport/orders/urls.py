from django.urls import path

from .views import OrderCreateView, OrderDetailView, OrderExcelExportView, OrderListView, OrderPdfExportView, OrderPdfView, OrderUpdateView

app_name = "orders"

urlpatterns = [
    path("", OrderListView.as_view(), name="customer-list"),
    path("export/pdf/", OrderPdfExportView.as_view(), name="list-export-pdf"),
    path("export/excel/", OrderExcelExportView.as_view(), name="list-export-excel"),
    path("create/", OrderCreateView.as_view(), name="create"),
    path("<uuid:pk>/edit/", OrderUpdateView.as_view(), name="edit"),
    path("<uuid:pk>/export-pdf/", OrderPdfView.as_view(), name="export-pdf"),
    path("<uuid:pk>/", OrderDetailView.as_view(), name="detail"),
]
