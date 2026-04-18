from django.contrib import admin

from .models import DeliveryReceipt, FuelPurchaseOrder, Supplier


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email")
    search_fields = ("name", "contact_person", "phone")


@admin.register(FuelPurchaseOrder)
class FuelPurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "supplier", "station", "fuel_type", "volume_liters", "unit_cost", "status")
    list_filter = ("status", "fuel_type")
    search_fields = ("reference", "supplier__name", "station__name")


@admin.register(DeliveryReceipt)
class DeliveryReceiptAdmin(admin.ModelAdmin):
    list_display = ("delivery_reference", "purchase_order", "tank", "delivered_volume", "status", "received_by", "created_at")
    list_filter = ("status", "purchase_order__status")
    search_fields = ("purchase_order__reference", "delivery_reference")
