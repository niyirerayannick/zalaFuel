from django.contrib import admin

from .models import Order, OrderDocument, OrderNote, OrderStatusHistory, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("name", "symbol", "measurement_category", "is_active", "created_at")
    list_filter = ("measurement_category", "is_active")
    search_fields = ("name", "symbol")
    ordering = ("name",)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer",
        "commodity_type",
        "total_quantity",
        "unit",
        "weight_kg",
        "quoted_price",
        "status",
        "created_at",
    )
    list_filter = ("status", "commodity_type", "payment_terms", "priority_level", "cargo_category")
    search_fields = ("order_number", "customer__company_name", "commodity_description")
    autocomplete_fields = (
        "customer",
        "cargo_category",
        "unit",
        "route",
        "approved_by",
        "assigned_trip",
        "assigned_vehicle",
        "assigned_driver",
        "created_by",
        "updated_by",
    )
    readonly_fields = ("order_number", "quantity", "created_at", "updated_at")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "previous_status", "new_status", "changed_by", "created_at")
    list_filter = ("previous_status", "new_status", "created_at")
    search_fields = ("order__order_number", "change_reason", "notes")
    autocomplete_fields = ("order", "changed_by")
    readonly_fields = ("created_at",)


@admin.register(OrderDocument)
class OrderDocumentAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "document_type", "uploaded_by", "uploaded_at")
    list_filter = ("document_type", "uploaded_at")
    search_fields = ("order__order_number", "name")
    autocomplete_fields = ("order", "uploaded_by")
    readonly_fields = ("uploaded_at",)


@admin.register(OrderNote)
class OrderNoteAdmin(admin.ModelAdmin):
    list_display = ("order", "created_by", "is_internal", "created_at")
    list_filter = ("is_internal", "created_at")
    search_fields = ("order__order_number", "note")
    autocomplete_fields = ("order", "created_by")
    readonly_fields = ("created_at",)
