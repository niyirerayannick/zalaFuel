from django.http import HttpResponse
from django.views.generic import TemplateView

from accounts.mixins import ReportsRoleMixin
from analytics.models import MarketShareSnapshot
from dispatches.models import Dispatch
from receipts.models import ProductReceipt
from revenue.models import RevenueEntry
from sales.models import OMCSalesEntry
from tanks.models import TankStockEntry


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(",".join(headers) + "\n")
    for row in rows:
        response.write(",".join(str(value) for value in row) + "\n")
    return response


class ReportsDashboardView(ReportsRoleMixin, TemplateView):
    template_name = "reports/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Reports",
                "active_menu": "reports",
                "report_cards": [
                    {"view_name": "reports:daily-tank-stock", "export_name": "reports:export-daily-tank-stock", "title": "Daily Tank Stock Report", "description": "Closing stock, computed stock, variance, utilization."},
                    {"view_name": "reports:terminal-stock", "export_name": "reports:export-daily-tank-stock", "title": "Terminal Stock Report", "description": "Stock position by terminal, tank, and product."},
                    {"view_name": "reports:product-receipts", "export_name": "reports:export-product-receipts", "title": "Product Receipt Report", "description": "Supplier, terminal, tank, and quantity received."},
                    {"view_name": "reports:dispatches", "export_name": "reports:export-dispatches", "title": "Dispatch Report", "description": "Dispatch destination, OMC, and terminal movement."},
                    {"view_name": "reports:omc-sales", "export_name": "reports:export-revenue", "title": "OMC Sales Report", "description": "Sales submissions by OMC and product."},
                    {"view_name": "reports:revenue", "export_name": "reports:export-revenue", "title": "Revenue Report", "description": "Revenue by OMC, product, and period."},
                    {"view_name": "reports:market-share", "export_name": "reports:revenue", "title": "Market Share Report", "description": "Latest market share ranking and product split."},
                    {"view_name": "reports:variance", "export_name": "reports:export-daily-tank-stock", "title": "Variance Report", "description": "Tank stock variance monitoring."},
                    {"view_name": "reports:annual-volume", "export_name": "reports:export-revenue", "title": "Annual Volume Analysis Report", "description": "Yearly product and OMC volume trend."},
                ],
            }
        )
        return context


class DailyTankStockReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/daily_tank_stock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Daily Tank Stock Report", "active_menu": "reports", "rows": TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").order_by("-entry_date")[:100]})
        return context


class TerminalStockReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/terminal_stock.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Terminal Stock Report", "active_menu": "reports", "rows": TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").order_by("-entry_date")[:100]})
        return context


class ProductReceiptReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/product_receipts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Product Receipt Report", "active_menu": "reports", "rows": ProductReceipt.objects.select_related("supplier", "terminal", "tank", "product").order_by("-receipt_date")[:100]})
        return context


class DispatchReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/dispatches.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Dispatch Report", "active_menu": "reports", "rows": Dispatch.objects.select_related("omc", "terminal", "tank", "product").order_by("-dispatch_date")[:100]})
        return context


class OMCSalesReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/omc_sales.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "OMC Sales Report", "active_menu": "reports", "rows": OMCSalesEntry.objects.select_related("omc", "terminal", "product").order_by("-sale_date")[:100]})
        return context


class RevenueReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/revenue.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Revenue Report", "active_menu": "reports", "rows": RevenueEntry.objects.select_related("omc", "terminal", "product").order_by("-revenue_date")[:100]})
        return context


class MarketShareReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/market_share.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Market Share Report", "active_menu": "reports", "rows": MarketShareSnapshot.objects.select_related("omc", "product").order_by("-snapshot_date", "-market_share_percent")[:100]})
        return context


class VarianceReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/variance.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Variance Report", "active_menu": "reports", "rows": TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").exclude(variance=0).order_by("-entry_date")[:100]})
        return context


class AnnualVolumeReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/annual_volume.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Annual Volume Analysis Report",
                "active_menu": "reports",
                "rows": OMCSalesEntry.objects.values("sale_date__year", "omc__name", "product__product_name").order_by("-sale_date__year", "omc__name", "product__product_name"),
            }
        )
        return context


class SimpleCsvExportView(ReportsRoleMixin, TemplateView):
    report_type = ""

    def get(self, request, *args, **kwargs):
        if self.report_type == "daily_tank_stock":
            rows = TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").values_list(
                "entry_date", "tank__terminal__name", "tank__name", "tank__product__product_name", "opening_stock", "stock_in", "stock_out", "closing_stock", "computed_stock", "variance"
            )
            return csv_response("daily_tank_stock.csv", ["Date", "Terminal", "Tank", "Product", "Opening", "Stock In", "Stock Out", "Closing", "Computed", "Variance"], rows)
        if self.report_type == "receipts":
            rows = ProductReceipt.objects.select_related("supplier", "terminal", "tank", "product").values_list(
                "receipt_date", "reference_number", "supplier__name", "product__product_name", "quantity_received", "terminal__name", "tank__name"
            )
            return csv_response("product_receipts.csv", ["Date", "Reference", "Supplier", "Product", "Quantity", "Terminal", "Tank"], rows)
        if self.report_type == "dispatches":
            rows = Dispatch.objects.select_related("omc", "terminal", "tank", "product").values_list(
                "dispatch_date", "reference_number", "omc__name", "product__product_name", "quantity_dispatched", "terminal__name", "destination"
            )
            return csv_response("dispatches.csv", ["Date", "Reference", "OMC", "Product", "Quantity", "Terminal", "Destination"], rows)
        rows = RevenueEntry.objects.select_related("omc", "terminal", "product").values_list(
            "revenue_date", "omc__name", "product__product_name", "volume_liters", "amount", "terminal__name"
        )
        return csv_response("revenue.csv", ["Date", "OMC", "Product", "Volume", "Amount", "Terminal"], rows)
