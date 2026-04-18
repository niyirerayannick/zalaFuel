from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from accounts.mixins import OperationsManageMixin

from .forms import ProductReceiptForm
from .models import ProductReceipt


class ProductReceiptListView(OperationsManageMixin, ListView):
    model = ProductReceipt
    template_name = "receipts/list.html"
    context_object_name = "receipts"

    def get_queryset(self):
        return ProductReceipt.objects.select_related("supplier", "product", "terminal", "tank").order_by("-receipt_date", "-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Product Receipts",
                "active_menu": "product_receipts",
                "total_quantity": ProductReceipt.objects.aggregate(total=Sum("quantity_received"))["total"] or 0,
            }
        )
        return context


class ProductReceiptCreateView(OperationsManageMixin, CreateView):
    model = ProductReceipt
    form_class = ProductReceiptForm
    template_name = "receipts/form.html"
    success_url = reverse_lazy("receipts:list")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"page_title": "New Receipt", "active_menu": "product_receipts"})
        return context

