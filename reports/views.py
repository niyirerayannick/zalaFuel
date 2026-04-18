from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.views.generic import TemplateView

from accounts.mixins import ReportsRoleMixin
from accounts.station_access import (
    filter_delivery_receipts_queryset_for_user,
    filter_fuel_sales_queryset_for_user,
    filter_inventory_records_queryset_for_user,
    filter_shifts_queryset_for_user,
    filter_tanks_queryset_for_user,
)
from finance.models import Payment
from inventory.models import FuelTank, InventoryRecord
from sales.models import FuelSale, ShiftSession
from suppliers.models import DeliveryReceipt


class ReportsDashboardView(ReportsRoleMixin, TemplateView):
    template_name = "reports/dashboard.html"
    extra_context = {"page_title": "Reports", "active_menu": "reports"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx.update(
            {
                "sales_total": filter_fuel_sales_queryset_for_user(FuelSale.objects.all(), user).aggregate(
                    s=Sum("total_amount")
                )["s"]
                or 0,
                "inventory_total": filter_tanks_queryset_for_user(FuelTank.objects.all(), user).aggregate(
                    s=Sum("current_volume_liters")
                )["s"]
                or 0,
                "shift_count": filter_shifts_queryset_for_user(ShiftSession.objects.all(), user).count(),
                "payments_total": Payment.objects.aggregate(s=Sum("amount"))["s"] or 0,
            }
        )
        return ctx


class SalesReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/sales.html"
    extra_context = {"page_title": "Sales Reports", "active_menu": "reports"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        sales = filter_fuel_sales_queryset_for_user(
            FuelSale.objects.select_related("shift", "shift__station", "nozzle"),
            user,
        ).order_by("-created_at")
        ctx.update(
            {
                "rows": sales[:100],
                "total_sales": sales.aggregate(s=Sum("total_amount"))["s"] or 0,
                "total_liters": sales.aggregate(s=Sum("volume_liters"))["s"] or 0,
            }
        )
        return ctx


class InventoryReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/inventory.html"
    extra_context = {"page_title": "Inventory Reports", "active_menu": "reports"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx.update(
            {
                "tanks": filter_tanks_queryset_for_user(
                    FuelTank.objects.select_related("station"),
                    user,
                ).order_by("station__name", "name"),
                "movements": filter_inventory_records_queryset_for_user(
                    InventoryRecord.objects.select_related("tank", "tank__station"),
                    user,
                ).order_by("-created_at")[:100],
            }
        )
        return ctx


class ShiftReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/shifts.html"
    extra_context = {"page_title": "Shift Reports", "active_menu": "reports"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["shifts"] = (
            filter_shifts_queryset_for_user(
                ShiftSession.objects.select_related("station", "attendant"),
                user,
            )
            .order_by("-opened_at")[:100]
        )
        return ctx


class FinancialReportView(ReportsRoleMixin, TemplateView):
    template_name = "reports/financial.html"
    extra_context = {"page_title": "Financial Reports", "active_menu": "reports"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        receipts = filter_delivery_receipts_queryset_for_user(
            DeliveryReceipt.objects.filter(status=DeliveryReceipt.Status.RECEIVED).exclude(unit_cost__isnull=True),
            user,
        )
        ctx.update(
            {
                "payments_total": Payment.objects.aggregate(s=Sum("amount"))["s"] or 0,
                "receipt_cost_total": receipts.annotate(
                    line_total=ExpressionWrapper(
                        F("delivered_volume") * F("unit_cost"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )
                ).aggregate(s=Sum("line_total"))["s"]
                or 0,
                "deliveries": receipts.select_related("purchase_order", "purchase_order__supplier", "tank").order_by(
                    "-delivery_date"
                )[:100],
                "payments": Payment.objects.select_related("invoice", "invoice__customer").order_by("-created_at")[:100],
            }
        )
        return ctx
