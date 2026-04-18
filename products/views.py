from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from accounts.mixins import AdminMixin

from .forms import ProductForm, SupplierForm
from .models import Product, Supplier


class ProductListView(AdminMixin, ListView):
    model = Product
    template_name = "products/list.html"
    context_object_name = "products"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        status = (self.request.GET.get("status") or "").strip().lower()
        product_type = (self.request.GET.get("product_type") or "").strip()

        products = Product.objects.order_by("display_order", "product_name")

        if search:
            products = products.filter(
                product_name__icontains=search
            ) | products.filter(product_code__icontains=search)
        if status:
            products = products.filter(status=status)
        if product_type:
            products = products.filter(product_type=product_type)

        return products

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_products = Product.objects.order_by("product_name")

        context.update(
            {
                "page_title": "Products",
                "active_menu": "administration",
                "total_products": all_products.count(),
                "active_products": all_products.filter(status=Product.Status.ACTIVE).count(),
                "inactive_products": all_products.filter(status=Product.Status.INACTIVE).count(),
                "kpi_categories": all_products.values("product_type").distinct().count(),
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "status": self.request.GET.get("status", ""),
                    "product_type": self.request.GET.get("product_type", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "products/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class ProductCreateView(AdminMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = "products/form.html"
    success_url = reverse_lazy("products:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["products/_modal_form.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add Product"
        context["action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)


class ProductDetailView(AdminMixin, DetailView):
    model = Product
    template_name = "products/detail.html"
    context_object_name = "product"


class ProductUpdateView(AdminMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = "products/form.html"
    success_url = reverse_lazy("products:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["products/_modal_form.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Product"
        context["action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)


class ProductToggleActiveView(AdminMixin, View):
    def post(self, request, *args, **kwargs):
        product = get_object_or_404(Product, pk=kwargs["pk"])
        product.status = (
            Product.Status.INACTIVE
            if product.status == Product.Status.ACTIVE
            else Product.Status.ACTIVE
        )
        product.save(update_fields=["status"])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect("products:list")


class SupplierListView(AdminMixin, ListView):
    model = Supplier
    template_name = "products/suppliers.html"
    context_object_name = "suppliers"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        status = (self.request.GET.get("status") or "").strip().lower()

        suppliers = Supplier.objects.order_by("supplier_name")

        if search:
            suppliers = suppliers.filter(
                supplier_name__icontains=search
            ) | suppliers.filter(supplier_code__icontains=search)
        if status:
            suppliers = suppliers.filter(status=status)

        return suppliers

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_suppliers = Supplier.objects.order_by("supplier_name")

        context.update(
            {
                "page_title": "Suppliers",
                "active_menu": "administration",
                "total_suppliers": all_suppliers.count(),
                "active_suppliers": all_suppliers.filter(status=Supplier.Status.ACTIVE).count(),
                "inactive_suppliers": all_suppliers.filter(status=Supplier.Status.INACTIVE).count(),
                "countries": all_suppliers.exclude(country__isnull=True).exclude(country__exact="").values("country").distinct().count(),
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "status": self.request.GET.get("status", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "products/suppliers/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class SupplierCreateView(AdminMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "products/suppliers/form.html"
    success_url = reverse_lazy("products:suppliers")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["products/suppliers/_modal_form.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Add Supplier"
        context["action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)


class SupplierDetailView(AdminMixin, DetailView):
    model = Supplier
    template_name = "products/suppliers/detail.html"
    context_object_name = "supplier"


class SupplierUpdateView(AdminMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = "products/suppliers/form.html"
    success_url = reverse_lazy("products:suppliers")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["products/suppliers/_modal_form.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Edit Supplier"
        context["action"] = self.request.path
        return context

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)


class SupplierToggleActiveView(AdminMixin, View):
    def post(self, request, *args, **kwargs):
        supplier = get_object_or_404(Supplier, pk=kwargs["pk"])
        supplier.status = (
            Supplier.Status.INACTIVE
            if supplier.status == Supplier.Status.ACTIVE
            else Supplier.Status.ACTIVE
        )
        supplier.save(update_fields=["status"])
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        return redirect("products:suppliers")

