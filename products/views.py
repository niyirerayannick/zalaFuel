from django.views.generic import CreateView, ListView, TemplateView
from django.urls import reverse_lazy

from accounts.mixins import AdminMixin

from .forms import ProductForm, SupplierForm
from .models import Product, Supplier


class ProductListView(AdminMixin, ListView):
    model = Product
    template_name = "products/list.html"
    context_object_name = "products"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "Products", "active_menu": "administration"})
        return context


class ProductCreateView(AdminMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/form.html"
    success_url = reverse_lazy("products:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Product", "active_menu": "administration"})
        return context


class SupplierListView(AdminMixin, TemplateView):
    template_name = "products/suppliers.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Suppliers",
                "active_menu": "administration",
                "suppliers": Supplier.objects.order_by("name"),
                "supplier_form": SupplierForm(),
            }
        )
        return context

