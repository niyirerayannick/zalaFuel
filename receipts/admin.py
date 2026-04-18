from django.contrib import admin

from .models import ProductReceipt


@admin.register(ProductReceipt)
class ProductReceiptAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "receipt_date", "product", "terminal", "tank", "quantity_received", "supplier")
    list_filter = ("receipt_date", "terminal", "product")
    search_fields = ("reference_number", "product__product_name", "supplier__name", "terminal__name")

