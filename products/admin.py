from django.contrib import admin

from .models import Product, Supplier


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "category", "default_price", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "code")


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email")
    search_fields = ("name", "contact_person", "email")

