from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from accounts.mixins import FinanceRoleMixin

from .forms import OMCSalesEntryForm
from .models import OMCSalesEntry


class OMCSalesDashboardView(FinanceRoleMixin, TemplateView):
    template_name = "sales/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        entries = OMCSalesEntry.objects.select_related("terminal", "omc", "product").order_by("-sale_date", "-created_at")
        context.update(
            {
                "page_title": "OMC Sales",
                "active_menu": "omc_sales",
                "entries": entries[:15],
                "sales_total": entries.aggregate(total=Sum("volume_liters"))["total"] or 0,
                "revenue_total": entries.aggregate(total=Sum("total_amount"))["total"] or 0,
                "by_omc": entries.values("omc__name").annotate(total_volume=Sum("volume_liters"), total_revenue=Sum("total_amount")).order_by("-total_volume"),
                "by_product": entries.values("product__name").annotate(total_volume=Sum("volume_liters"), total_revenue=Sum("total_amount")).order_by("-total_volume"),
            }
        )
        return context


class OMCSalesEntryCreateView(FinanceRoleMixin, CreateView):
    model = OMCSalesEntry
    form_class = OMCSalesEntryForm
    template_name = "sales/form.html"
    success_url = reverse_lazy("sales:dashboard")

    def form_valid(self, form):
        form.instance.submitted_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Sales Entry", "active_menu": "omc_sales"})
        return context
