from django.urls import path
from . import views

app_name = 'trips'

urlpatterns = [
    path("operations/dashboard/", views.OperationsDashboardView.as_view(), name="operations-dashboard"),
    path("shipments/", views.ShipmentListView.as_view(), name="shipment-list"),
    path("shipments/export/pdf/", views.ShipmentPdfExportView.as_view(), name="shipment-export-pdf"),
    path("shipments/export/excel/", views.ShipmentExcelExportView.as_view(), name="shipment-export-excel"),
    path("shipments/<int:pk>/edit/", views.ShipmentUpdateView.as_view(), name="shipment-edit"),
    path("", views.TripListView.as_view(), name="list"),
    path("export/pdf/", views.TripListPdfExportView.as_view(), name="list-export-pdf"),
    path("export/excel/", views.TripListExcelExportView.as_view(), name="list-export-excel"),
    path("create/", views.TripCreateView.as_view(), name="create"),
    path("<int:pk>/", views.TripDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.TripUpdateView.as_view(), name="edit"),
    path("<int:trip_id>/report/pdf/", views.export_trip_report_pdf, name="report-pdf"),
    path("<int:trip_id>/report/excel/", views.export_trip_report_excel, name="report-excel"),
    path("<int:trip_id>/report/email/", views.email_trip_report, name="report-email"),
    path("<int:trip_id>/status/", views.update_trip_status, name="status-update"),
    path("<int:trip_id>/invoice/generate/", views.generate_trip_invoice, name="invoice-generate"),
    path("<int:trip_id>/loading-order/send/", views.send_trip_loading_order, name="loading-order-send"),
    path("<int:trip_id>/expenses/add/", views.add_trip_expense, name="expense-add"),
    path("<int:trip_id>/expenses/<int:expense_id>/edit/", views.edit_trip_expense, name="expense-edit"),
    path("<int:trip_id>/expenses/<int:expense_id>/delete/", views.delete_trip_expense, name="expense-delete"),
    path("<int:trip_id>/shipments/add/", views.add_trip_shipment, name="shipment-add"),
    path("<int:trip_id>/allowances/request/", views.request_allowance, name="allowance-request"),
    path("allowances/<int:allowance_id>/approve/", views.approve_trip_allowance, name="allowance-approve"),
]
