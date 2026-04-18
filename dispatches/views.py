from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from django.views import View
from django.shortcuts import get_object_or_404

from accounts.mixins import OperationsManageMixin

from .forms import DispatchForm
from .models import Dispatch


class DispatchListView(OperationsManageMixin, ListView):
    model = Dispatch
    template_name = "dispatches/list.html"
    context_object_name = "dispatches"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        omc_filter = (self.request.GET.get("omc") or "").strip()
        product_filter = (self.request.GET.get("product") or "").strip()
        terminal_filter = (self.request.GET.get("terminal") or "").strip()

        dispatches = Dispatch.objects.select_related("product", "terminal", "tank", "omc").order_by("-dispatch_date", "-created_at")

        if search:
            dispatches = dispatches.filter(
                reference_number__icontains=search
            ) | dispatches.filter(destination__icontains=search)
        if omc_filter:
            dispatches = dispatches.filter(omc_id=omc_filter)
        if product_filter:
            dispatches = dispatches.filter(product_id=product_filter)
        if terminal_filter:
            dispatches = dispatches.filter(terminal_id=terminal_filter)

        return dispatches

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_dispatches = Dispatch.objects.select_related("product", "terminal", "omc")

        context.update(
            {
                "page_title": "Dispatches",
                "active_menu": "dispatches",
                "kpi_total_volume": all_dispatches.aggregate(total=Sum("quantity_dispatched"))["total"] or 0,
                "kpi_today": all_dispatches.filter(dispatch_date__isnull=False).count(),
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "omc": self.request.GET.get("omc", ""),
                    "product": self.request.GET.get("product", ""),
                    "terminal": self.request.GET.get("terminal", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "dispatches/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class DispatchCreateView(OperationsManageMixin, CreateView):
    model = Dispatch
    form_class = DispatchForm
    template_name = "dispatches/form.html"
    success_url = reverse_lazy("dispatches:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["dispatches/_modal_form.html"]
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
        context["title"] = "Add Dispatch"
        context["action"] = self.request.path
        return context


class DispatchUpdateView(OperationsManageMixin, UpdateView):
    model = Dispatch
    form_class = DispatchForm
    template_name = "dispatches/form.html"
    success_url = reverse_lazy("dispatches:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["dispatches/_modal_form.html"]
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
        context["title"] = "Edit Dispatch"
        context["action"] = self.request.path
        return context

