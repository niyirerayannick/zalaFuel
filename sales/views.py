from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, UpdateView
from django.shortcuts import get_object_or_404

from accounts.mixins import FinanceRoleMixin

from .forms import OMCSalesEntryForm
from .models import OMCSalesEntry


class OMCSalesDashboardView(FinanceRoleMixin, ListView):
    model = OMCSalesEntry
    template_name = "sales/dashboard.html"
    context_object_name = "entries"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        omc_filter = self.request.GET.get("omc") or ""
        product_filter = self.request.GET.get("product") or ""
        terminal_filter = self.request.GET.get("terminal") or ""
        date_from = self.request.GET.get("date_from") or ""
        date_to = self.request.GET.get("date_to") or ""

        entries = OMCSalesEntry.objects.select_related("terminal", "omc", "product").order_by("-sale_date", "-created_at")

        if search:
            entries = entries.filter(
                submission_reference__icontains=search
            ) | entries.filter(omc__name__icontains=search)
        if omc_filter:
            entries = entries.filter(omc_id=omc_filter)
        if product_filter:
            entries = entries.filter(product_id=product_filter)
        if terminal_filter:
            entries = entries.filter(terminal_id=terminal_filter)
        if date_from:
            entries = entries.filter(sale_date__gte=date_from)
        if date_to:
            entries = entries.filter(sale_date__lte=date_to)

        return entries

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_entries = OMCSalesEntry.objects.select_related("terminal", "omc", "product")

        total_volume = all_entries.aggregate(total=Sum("volume_liters"))["total"] or 0
        total_revenue = all_entries.aggregate(total=Sum("total_amount"))["total"] or 0
        active_omcs = all_entries.values("omc").distinct().count()

        top_by_volume = all_entries.order_by("-volume_liters").first()
        top_by_revenue = all_entries.order_by("-total_amount").first()

        context.update(
            {
                "page_title": "OMC Sales",
                "active_menu": "omc_sales",
                "kpi_total_volume": total_volume,
                "kpi_total_revenue": total_revenue,
                "kpi_active_omcs": active_omcs,
                "kpi_total_records": all_entries.count(),
                "kpi_top_volume_omc": top_by_volume.omc.name if top_by_volume else "-",
                "kpi_top_revenue_omc": top_by_revenue.omc.name if top_by_revenue else "-",
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "omc": self.request.GET.get("omc", ""),
                    "product": self.request.GET.get("product", ""),
                    "terminal": self.request.GET.get("terminal", ""),
                    "date_from": self.request.GET.get("date_from", ""),
                    "date_to": self.request.GET.get("date_to", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "sales/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class OMCSalesEntryCreateView(FinanceRoleMixin, CreateView):
    model = OMCSalesEntry
    form_class = OMCSalesEntryForm
    template_name = "sales/form.html"
    success_url = reverse_lazy("sales:dashboard")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["sales/_modal_form.html"]
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
        context["title"] = "Add Sales Entry"
        context["action"] = self.request.path
        return context


class OMCSalesEntryUpdateView(FinanceRoleMixin, UpdateView):
    model = OMCSalesEntry
    form_class = OMCSalesEntryForm
    template_name = "sales/form.html"
    success_url = reverse_lazy("sales:dashboard")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["sales/_modal_form.html"]
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
        context["title"] = "Edit Sales Entry"
        context["action"] = self.request.path
        return context
