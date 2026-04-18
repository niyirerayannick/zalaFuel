from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from accounts.mixins import AdminMixin

from .forms import OMCForm
from .models import OMC


class OMCListView(AdminMixin, ListView):
    model = OMC
    template_name = "omcs/list.html"
    context_object_name = "omcs"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "OMC Sales", "active_menu": "omc_sales"})
        return context


class OMCCreateView(AdminMixin, CreateView):
    model = OMC
    form_class = OMCForm
    template_name = "omcs/form.html"
    success_url = reverse_lazy("omcs:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New OMC", "active_menu": "administration"})
        return context

