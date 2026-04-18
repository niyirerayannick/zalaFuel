from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from accounts.mixins import OperationsManageMixin

from .forms import DispatchForm
from .models import Dispatch


class DispatchListView(OperationsManageMixin, ListView):
    model = Dispatch
    template_name = "dispatches/list.html"
    context_object_name = "dispatches"

    def get_queryset(self):
        return Dispatch.objects.select_related("product", "terminal", "tank", "omc").order_by("-dispatch_date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Dispatches",
                "active_menu": "dispatches",
                "total_quantity": Dispatch.objects.aggregate(total=Sum("quantity_dispatched"))["total"] or 0,
            }
        )
        return context


class DispatchCreateView(OperationsManageMixin, CreateView):
    model = Dispatch
    form_class = DispatchForm
    template_name = "dispatches/form.html"
    success_url = reverse_lazy("dispatches:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Dispatch", "active_menu": "dispatches"})
        return context

