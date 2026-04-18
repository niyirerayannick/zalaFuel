from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.shortcuts import get_object_or_404

from accounts.mixins import OperationsManageMixin

from .forms import TankForm, TankStockEntryForm
from .models import Tank, TankStockEntry


class TankListView(OperationsManageMixin, ListView):
    model = Tank
    template_name = "tanks/list.html"
    context_object_name = "tanks"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        terminal_filter = (self.request.GET.get("terminal") or "").strip()
        product_filter = (self.request.GET.get("product") or "").strip()

        tanks = Tank.objects.select_related("terminal", "product").order_by("terminal__name", "name")

        if search:
            tanks = tanks.filter(name__icontains=search) | tanks.filter(terminal__name__icontains=search)
        if terminal_filter:
            tanks = tanks.filter(terminal_id=terminal_filter)
        if product_filter:
            tanks = tanks.filter(product_id=product_filter)

        return tanks

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_tanks = Tank.objects.select_related("terminal", "product")

        total_stock = sum(t.current_stock_liters or 0 for t in all_tanks)
        low_stock = sum(1 for t in all_tanks if t.current_stock_liters and t.current_stock_liters < t.minimum_threshold)

        context.update(
            {
                "page_title": "Tank Stocks",
                "active_menu": "tank_stocks",
                "stock_summary": TankStockEntry.objects.aggregate(
                    opening=Sum("opening_stock"),
                    stock_in=Sum("stock_in"),
                    stock_out=Sum("stock_out"),
                    closing=Sum("closing_stock"),
                    variance=Sum("variance"),
                ),
                "kpi_total": all_tanks.count(),
                "kpi_total_stock": total_stock,
                "kpi_low": low_stock,
                "kpi_capacity_util": sum(t.utilization_percent for t in all_tanks) / all_tanks.count() if all_tanks.exists() else 0,
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "terminal": self.request.GET.get("terminal", ""),
                    "product": self.request.GET.get("product", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "tanks/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class TankCreateView(OperationsManageMixin, CreateView):
    model = Tank
    form_class = TankForm
    template_name = "tanks/form.html"
    success_url = reverse_lazy("tanks:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["tanks/_modal_form.html"]
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
        context["title"] = "Add Tank"
        context["action"] = self.request.path
        return context


class TankUpdateView(OperationsManageMixin, UpdateView):
    model = Tank
    form_class = TankForm
    template_name = "tanks/form.html"
    success_url = reverse_lazy("tanks:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["tanks/_modal_form.html"]
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
        context["title"] = "Edit Tank"
        context["action"] = self.request.path
        return context


class TankStockEntryCreateView(OperationsManageMixin, CreateView):
    model = TankStockEntry
    form_class = TankStockEntryForm
    template_name = "tanks/entry_form.html"
    success_url = reverse_lazy("tanks:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["tanks/_entry_modal_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
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
        context["title"] = "Daily Tank Stock Entry"
        context["action"] = self.request.path
        return context


class TankEntryHistoryView(OperationsManageMixin, TemplateView):
    template_name = "tanks/history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Tank Stock History",
                "active_menu": "tank_stocks",
                "entries": TankStockEntry.objects.select_related("tank", "tank__terminal", "tank__product").order_by("-entry_date"),
            }
        )
        return context

