from django.db.models import Count, Sum
from django.views.generic import CreateView, DetailView, ListView, TemplateView
from django.urls import reverse_lazy

from accounts.mixins import OperationsManageMixin
from dispatches.models import Dispatch
from receipts.models import ProductReceipt
from tanks.models import Tank, TankStockEntry

from .forms import TerminalForm
from .models import Terminal, TerminalActivityLog


class TerminalListView(OperationsManageMixin, ListView):
    model = Terminal
    template_name = "terminals/list.html"
    context_object_name = "terminals"

    def get_queryset(self):
        return Terminal.objects.select_related("manager").annotate(
            tank_count=Count("tanks", distinct=True),
            stock_total=Sum("tanks__current_stock_liters"),
        ).order_by("name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Terminal Operations", "active_menu": "terminal_operations"})
        return context


class TerminalCreateView(OperationsManageMixin, CreateView):
    model = Terminal
    form_class = TerminalForm
    template_name = "terminals/form.html"
    success_url = reverse_lazy("terminals:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Terminal", "active_menu": "terminal_operations"})
        return context


class TerminalDetailView(OperationsManageMixin, DetailView):
    model = Terminal
    template_name = "terminals/detail.html"
    context_object_name = "terminal"

    def get_queryset(self):
        return Terminal.objects.select_related("manager")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        terminal = self.object
        context.update(
            {
                "page_title": terminal.name,
                "active_menu": "terminal_operations",
                "tanks": Tank.objects.filter(terminal=terminal).select_related("product"),
                "receipts": ProductReceipt.objects.filter(terminal=terminal).select_related("product", "supplier").order_by("-receipt_date")[:8],
                "dispatches": Dispatch.objects.filter(terminal=terminal).select_related("product", "omc").order_by("-dispatch_date")[:8],
                "stock_entries": TankStockEntry.objects.filter(tank__terminal=terminal).select_related("tank", "tank__product").order_by("-entry_date")[:8],
                "activity_logs": TerminalActivityLog.objects.filter(terminal=terminal).order_by("-event_time")[:10],
            }
        )
        return context


class TerminalStatusView(OperationsManageMixin, TemplateView):
    template_name = "terminals/status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Terminal Status",
                "active_menu": "terminal_operations",
                "terminals": Terminal.objects.annotate(
                    tank_count=Count("tanks", distinct=True),
                    stock_total=Sum("tanks__current_stock_liters"),
                ).order_by("name"),
            }
        )
        return context


class TerminalActivityLogView(OperationsManageMixin, ListView):
    model = TerminalActivityLog
    template_name = "terminals/activity.html"
    context_object_name = "logs"

    def get_queryset(self):
        return TerminalActivityLog.objects.select_related("terminal").order_by("-event_time", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Terminal Activity Log", "active_menu": "terminal_operations"})
        return context
