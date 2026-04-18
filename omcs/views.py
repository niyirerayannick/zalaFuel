from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from accounts.mixins import AdminMixin

from .forms import OMCForm
from .models import OMC


class OMCListView(AdminMixin, ListView):
    model = OMC
    template_name = "omcs/list.html"
    context_object_name = "omcs"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        status = (self.request.GET.get("status") or "").strip().lower()

        omcs = OMC.objects.order_by("name")

        if search:
            omcs = omcs.filter(
                name__icontains=search
            ) | omcs.filter(code__icontains=search)
        if status:
            is_active = status == "active"
            omcs = omcs.filter(is_active=is_active)

        return omcs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_omcs = OMC.objects.order_by("name")

        context.update(
            {
                "page_title": "OMC Sales",
                "active_menu": "omc_sales",
                "total_omcs": all_omcs.count(),
                "active_omcs": all_omcs.filter(is_active=True).count(),
                "inactive_omcs": all_omcs.filter(is_active=False).count(),
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "status": self.request.GET.get("status", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "omcs/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class OMCCreateView(AdminMixin, CreateView):
    model = OMC
    form_class = OMCForm
    template_name = "omcs/form.html"
    success_url = reverse_lazy("omcs:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["omcs/_modal_form.html"]
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
        context["title"] = "Add OMC"
        context["action"] = self.request.path
        return context


class OMCUpdateView(AdminMixin, UpdateView):
    model = OMC
    form_class = OMCForm
    template_name = "omcs/form.html"
    success_url = reverse_lazy("omcs:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["omcs/_modal_form.html"]
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
        context["title"] = "Edit OMC"
        context["action"] = self.request.path
        return context

