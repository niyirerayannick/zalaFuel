from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.shortcuts import get_object_or_404

from accounts.mixins import FinanceRoleMixin

from .forms import RevenueEntryForm
from .models import RevenueEntry


class RevenueDashboardView(FinanceRoleMixin, ListView):
    model = RevenueEntry
    template_name = "revenue/dashboard.html"
    context_object_name = "entries"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        omc_filter = self.request.GET.get("omc") or ""
        product_filter = self.request.GET.get("product") or ""
        terminal_filter = self.request.GET.get("terminal") or ""
        year = self.request.GET.get("year") or ""

        entries = RevenueEntry.objects.select_related("terminal", "omc", "product").order_by("-revenue_date", "-created_at")

        if search:
            entries = entries.filter(omc__name__icontains=search) | entries.filter(product__product_name__icontains=search)
        if omc_filter:
            entries = entries.filter(omc_id=omc_filter)
        if product_filter:
            entries = entries.filter(product_id=product_filter)
        if terminal_filter:
            entries = entries.filter(terminal_id=terminal_filter)
        if year:
            entries = entries.filter(revenue_date__year=year)

        return entries

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_entries = RevenueEntry.objects.select_related("terminal", "omc", "product")

        total_revenue = all_entries.aggregate(total=Sum("amount"))["total"] or 0
        total_volume = all_entries.aggregate(total=Sum("volume_liters"))["total"] or 0
        active_omcs = all_entries.values("omc").distinct().count()

        top_by_revenue = all_entries.order_by("-amount").first()
        top_by_volume = all_entries.order_by("-volume_liters").first()

        context.update(
            {
                "page_title": "Revenue Analysis",
                "active_menu": "revenue_analysis",
                "kpi_total_revenue": total_revenue,
                "kpi_total_volume": total_volume,
                "kpi_active_omcs": active_omcs,
                "kpi_total_records": all_entries.count(),
                "kpi_top_revenue_omc": top_by_revenue.omc.name if top_by_revenue else "-",
                "kpi_top_volume_product": top_by_volume.product.product_name if top_by_volume else "-",
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "omc": self.request.GET.get("omc", ""),
                    "product": self.request.GET.get("product", ""),
                    "terminal": self.request.GET.get("terminal", ""),
                    "year": self.request.GET.get("year", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "revenue/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class RevenueEntryCreateView(FinanceRoleMixin, CreateView):
    model = RevenueEntry
    form_class = RevenueEntryForm
    template_name = "revenue/form.html"
    success_url = reverse_lazy("revenue:dashboard")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["revenue/_modal_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        form.instance.created_by = self.request.user
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
        context["title"] = "Add Revenue Entry"
        context["action"] = self.request.path
        return context


class RevenueEntryUpdateView(FinanceRoleMixin, UpdateView):
    model = RevenueEntry
    form_class = RevenueEntryForm
    template_name = "revenue/form.html"
    success_url = reverse_lazy("revenue:dashboard")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["revenue/_modal_form.html"]
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
        context["title"] = "Edit Revenue Entry"
        context["action"] = self.request.path
        return context

