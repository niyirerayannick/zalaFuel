from django.contrib import admin

from .models import CargoCategory, Shipment, Trip


@admin.register(CargoCategory)
class CargoCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "route",
        "vehicle",
        "driver",
        "status",
        "distance",
        "revenue",
        "profit",
    )
    list_filter = ("status", "commodity_type")
    search_fields = ("order_number", "customer__company_name", "vehicle__plate_number", "driver__name")
    autocomplete_fields = ("customer", "commodity_type", "route", "vehicle", "driver")


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order",
        "customer",
        "trip",
        "quantity",
        "weight_kg",
        "carriage_type",
        "status",
        "created_at",
    )
    list_filter = ("status", "carriage_type", "created_at")
    search_fields = ("order__order_number", "customer__company_name", "container_number")
    autocomplete_fields = ("trip", "order", "customer")
