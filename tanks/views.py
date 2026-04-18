from django.db.models import Avg, Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView

from accounts.mixins import OperationsManageMixin

from .forms import TankForm, TankStockEntryForm
from .models import Tank, TankStockEntry


class TankListView(OperationsManageMixin, ListView):
    model = Tank
    template_name = "tanks/list.html"
    context_object_name = "tanks"

    def get_queryset(self):
        return Tank.objects.select_related("terminal", "product").order_by("terminal__name", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Tank Stocks",
                "active_menu": "tank_stocks",
                "entry_form": TankStockEntryForm(),
                "tank_form": TankForm(),
                "stock_summary": TankStockEntry.objects.aggregate(
                    opening=Sum("opening_stock"),
                    stock_in=Sum("stock_in"),
                    stock_out=Sum("stock_out"),
                    closing=Sum("closing_stock"),
                    variance=Sum("variance"),
                ),
                "utilization_average": Tank.objects.aggregate(avg=Avg("current_stock_liters"))["avg"] or 0,
            }
        )
        return context


class TankCreateView(OperationsManageMixin, CreateView):
    model = Tank
    form_class = TankForm
    template_name = "tanks/form.html"
    success_url = reverse_lazy("tanks:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Tank", "active_menu": "administration"})
        return context


class TankStockEntryCreateView(OperationsManageMixin, CreateView):
    model = TankStockEntry
    form_class = TankStockEntryForm
    template_name = "tanks/entry_form.html"
    success_url = reverse_lazy("tanks:list")

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Daily Tank Stock Entry", "active_menu": "tank_stocks"})
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

