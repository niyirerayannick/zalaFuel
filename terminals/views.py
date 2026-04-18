from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

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
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        status = (self.request.GET.get("status") or "").strip().lower()

        terminals = Terminal.objects.select_related("manager").annotate(
            tank_count=Count("tanks", distinct=True),
            stock_total=Sum("tanks__current_stock_liters"),
        ).order_by("name")

        if search:
            terminals = terminals.filter(name__icontains=search) | terminals.filter(location__icontains=search)
        if status:
            is_active = status == "active"
            terminals = terminals.filter(is_active=is_active)

        return terminals

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_terminals = Terminal.objects.select_related("manager")

        context.update(
            {
                "page_title": "Terminal Operations",
                "active_menu": "terminal_operations",
                "kpi_total": all_terminals.count(),
                "kpi_active": all_terminals.filter(is_active=True).count(),
                "kpi_tanks": all_terminals.aggregate(total=Count("tanks", distinct=True))["total"] or 0,
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "status": self.request.GET.get("status", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "terminals/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class TerminalCreateView(OperationsManageMixin, CreateView):
    model = Terminal
    form_class = TerminalForm
    template_name = "terminals/form.html"
    success_url = reverse_lazy("terminals:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["terminals/_modal_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add Terminal"
        context["action"] = self.request.path
        return context


class TerminalUpdateView(OperationsManageMixin, UpdateView):
    model = Terminal
    form_class = TerminalForm
    template_name = "terminals/form.html"
    success_url = reverse_lazy("terminals:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["terminals/_modal_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Terminal"
        context["action"] = self.request.path
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
