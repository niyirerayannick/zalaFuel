from django.urls import path
from . import views

app_name = 'finance'

# Finance management endpoints
urlpatterns = [
    # Dashboard / Overview
    path("", views.FinanceDashboardView.as_view(), name="dashboard"),
    path("overview/", views.FinanceOverviewView.as_view(), name="overview"),
    path("analysis/export/excel/", views.FinanceAnalysisExcelExportView.as_view(), name="analysis-export-excel"),
    path("analysis/export/pdf/", views.FinanceAnalysisPdfExportView.as_view(), name="analysis-export-pdf"),
    
    # Payments
    path("payments/", views.PaymentListView.as_view(), name="payment-list"),
    path("payments/export/excel/", views.PaymentExcelExportView.as_view(), name="payment-export-excel"),
    path("payments/export/pdf/", views.PaymentPdfExportView.as_view(), name="payment-export-pdf"),
    path("payments/create/", views.PaymentCreateView.as_view(), name="payment-create"),
    path("payments/<int:pk>/invoice.pdf", views.PaymentInvoicePdfView.as_view(), name="payment-invoice-pdf"),
    path("payments/<int:pk>/verify/", views.PaymentInvoiceVerifyView.as_view(), name="payment-invoice-verify"),
    path("payments/<int:pk>/", views.PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<int:pk>/edit/", views.PaymentUpdateView.as_view(), name="payment-edit"),
    
    # Expenses
    path("expenses/", views.ExpenseListView.as_view(), name="expense-list"),
    path("expenses/export/excel/", views.ExpenseExcelExportView.as_view(), name="expense-export-excel"),
    path("expenses/export/pdf/", views.ExpensePdfExportView.as_view(), name="expense-export-pdf"),
    path("expenses/create/", views.ExpenseCreateView.as_view(), name="expense-create"),
    path("expenses/<int:pk>/", views.ExpenseDetailView.as_view(), name="expense-detail"),
    path("expenses/<int:pk>/edit/", views.ExpenseUpdateView.as_view(), name="expense-edit"),

    # Driver fees
    path("driver-fees/", views.DriverFeeListView.as_view(), name="driverfee-list"),
    path("driver-fees/create/", views.DriverFeeCreateView.as_view(), name="driverfee-create"),
]
