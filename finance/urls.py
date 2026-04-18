from django.urls import path

from .views import (
    CustomerListView,
    CustomerCreateView,
    CustomerDeleteView,
    CustomerCreditPaymentCreateView,
    ExpenseListView,
    FinanceDashboardView,
    RevenueListView,
    CustomerExportCSVView,
    CustomerExportExcelView,
    CustomerExportPDFView,
    CustomerUpdateView,
)

app_name = "finance"

urlpatterns = [
    path("", FinanceDashboardView.as_view(), name="dashboard"),
    path("revenue/", RevenueListView.as_view(), name="revenue"),
    path("expenses/", ExpenseListView.as_view(), name="expenses"),
    path("customers/", CustomerListView.as_view(), name="customers"),
    path("customers/create/", CustomerCreateView.as_view(), name="customers-create"),
    path("customers/<int:pk>/edit/", CustomerUpdateView.as_view(), name="customers-update"),
    path("customers/<int:pk>/delete/", CustomerDeleteView.as_view(), name="customers-delete"),
    path("customers/<int:pk>/credit-payment/", CustomerCreditPaymentCreateView.as_view(), name="customers-credit-payment"),
    path("customers/export/csv/", CustomerExportCSVView.as_view(), name="customers-export-csv"),
    path("customers/export/excel/", CustomerExportExcelView.as_view(), name="customers-export-excel"),
    path("customers/export/pdf/", CustomerExportPDFView.as_view(), name="customers-export-pdf"),
]
