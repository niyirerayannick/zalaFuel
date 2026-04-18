from django.urls import path

from .views import (
    AnnualVolumeReportView,
    DailyTankStockReportView,
    DispatchReportView,
    MarketShareReportView,
    OMCSalesReportView,
    ProductReceiptReportView,
    ReportsDashboardView,
    RevenueReportView,
    SimpleCsvExportView,
    TerminalStockReportView,
    VarianceReportView,
)

app_name = "reports"

urlpatterns = [
    path("", ReportsDashboardView.as_view(), name="dashboard"),
    path("daily-tank-stock/", DailyTankStockReportView.as_view(), name="daily-tank-stock"),
    path("terminal-stock/", TerminalStockReportView.as_view(), name="terminal-stock"),
    path("product-receipts/", ProductReceiptReportView.as_view(), name="product-receipts"),
    path("dispatches/", DispatchReportView.as_view(), name="dispatches"),
    path("omc-sales/", OMCSalesReportView.as_view(), name="omc-sales"),
    path("revenue/", RevenueReportView.as_view(), name="revenue"),
    path("market-share/", MarketShareReportView.as_view(), name="market-share"),
    path("variance/", VarianceReportView.as_view(), name="variance"),
    path("annual-volume/", AnnualVolumeReportView.as_view(), name="annual-volume"),
    path("export/daily-tank-stock/", SimpleCsvExportView.as_view(report_type="daily_tank_stock"), name="export-daily-tank-stock"),
    path("export/product-receipts/", SimpleCsvExportView.as_view(report_type="receipts"), name="export-product-receipts"),
    path("export/dispatches/", SimpleCsvExportView.as_view(report_type="dispatches"), name="export-dispatches"),
    path("export/revenue/", SimpleCsvExportView.as_view(report_type="revenue"), name="export-revenue"),
]
