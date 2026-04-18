from django.contrib import admin

from .models import Product, Supplier


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("product_name", "product_code", "product_type", "status", "display_order")
    list_filter = ("product_type", "status")
    search_fields = ("product_name", "product_code")
    ordering = ("display_order", "product_name")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("supplier_name", "supplier_code", "contact_person", "phone", "email", "status")
    list_filter = ("status", "country")
    search_fields = ("supplier_name", "supplier_code", "contact_person", "email")
    ordering = ("supplier_name",)

