from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from accounts.mixins import FinanceRoleMixin

from .forms import RevenueEntryForm
from .models import RevenueEntry


class RevenueDashboardView(FinanceRoleMixin, TemplateView):
    template_name = "revenue/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        revenue_entries = RevenueEntry.objects.select_related("terminal", "product", "omc").order_by("-revenue_date")
        context.update(
            {
                "page_title": "Revenue Analysis",
                "active_menu": "revenue_analysis",
                "entries": revenue_entries[:12],
                "revenue_total": revenue_entries.aggregate(total=Sum("amount"))["total"] or 0,
                "volume_total": revenue_entries.aggregate(total=Sum("volume_liters"))["total"] or 0,
                "by_omc": revenue_entries.values("omc__name").annotate(total=Sum("amount")).order_by("-total"),
                "by_product": revenue_entries.values("product__name").annotate(total=Sum("amount")).order_by("-total"),
                "yearly_summary": revenue_entries.values("revenue_date__year").annotate(total=Sum("amount"), volume=Sum("volume_liters")).order_by("-revenue_date__year"),
            }
        )
        return context


class RevenueEntryCreateView(FinanceRoleMixin, CreateView):
    model = RevenueEntry
    form_class = RevenueEntryForm
    template_name = "revenue/form.html"
    success_url = reverse_lazy("revenue:dashboard")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Revenue Entry", "active_menu": "revenue_analysis"})
        return context

