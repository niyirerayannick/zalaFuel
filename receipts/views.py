from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from accounts.mixins import OperationsManageMixin
from products.models import Product, Supplier
from terminals.models import Terminal

from .forms import ProductReceiptForm
from .models import ProductReceipt


class ProductReceiptListView(OperationsManageMixin, ListView):
    model = ProductReceipt
    template_name = "receipts/list.html"
    context_object_name = "receipts"
    paginate_by = 25

    def get_queryset(self):
        search = (self.request.GET.get("search") or "").strip().lower()
        supplier_filter = (self.request.GET.get("supplier") or "").strip()
        product_filter = (self.request.GET.get("product") or "").strip()
        terminal_filter = (self.request.GET.get("terminal") or "").strip()

        receipts = ProductReceipt.objects.select_related("supplier", "product", "terminal", "tank").order_by("-receipt_date", "-created_at")

        if search:
            receipts = receipts.filter(
                reference_number__icontains=search
            ) | receipts.filter(waybill_number__icontains=search)
        if supplier_filter:
            receipts = receipts.filter(supplier_id=supplier_filter)
        if product_filter:
            receipts = receipts.filter(product_id=product_filter)
        if terminal_filter:
            receipts = receipts.filter(terminal_id=terminal_filter)

        return receipts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_receipts = ProductReceipt.objects.select_related("product", "supplier", "terminal")

        context.update(
            {
                "page_title": "Product Receipts",
                "active_menu": "product_receipts",
                "kpi_total_volume": all_receipts.aggregate(total=Sum("quantity_received"))["total"] or 0,
                "kpi_today": all_receipts.count(),
                "suppliers": Supplier.objects.order_by("supplier_name"),
                "products": Product.objects.order_by("product_name"),
                "terminals": Terminal.objects.order_by("name"),
                "filters": {
                    "search": self.request.GET.get("search", ""),
                    "supplier": self.request.GET.get("supplier", ""),
                    "product": self.request.GET.get("product", ""),
                    "terminal": self.request.GET.get("terminal", ""),
                },
            }
        )
        return context

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "receipts/_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class ProductReceiptCreateView(OperationsManageMixin, CreateView):
    model = ProductReceipt
    form_class = ProductReceiptForm
    template_name = "receipts/form.html"
    success_url = reverse_lazy("receipts:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["receipts/_modal_form.html"]
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
        context["title"] = "Add Receipt"
        context["action"] = self.request.path
        return context


class ProductReceiptUpdateView(OperationsManageMixin, UpdateView):
    model = ProductReceipt
    form_class = ProductReceiptForm
    template_name = "receipts/form.html"
    success_url = reverse_lazy("receipts:list")

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["receipts/_modal_form.html"]
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
        context["title"] = "Edit Receipt"
        context["action"] = self.request.path
        return context
