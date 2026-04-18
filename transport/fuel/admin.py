from django.contrib import admin

from .models import FuelDocument, FuelRequest, FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ("name", "location")
    search_fields = ("name", "location")


@admin.register(FuelRequest)
class FuelRequestAdmin(admin.ModelAdmin):
    list_display = (
        "trip",
        "driver",
        "station",
        "amount",
        "is_approved",
        "posted_to_trip",
        "approved_by",
        "approved_at",
        "created_at",
    )
    list_filter = ("is_approved", "posted_to_trip", "station")
    search_fields = ("trip__order_number", "driver__username", "station__name")
    autocomplete_fields = ("trip", "driver", "station", "approved_by")


@admin.register(FuelDocument)
class FuelDocumentAdmin(admin.ModelAdmin):
    list_display = ("fuel_request", "uploaded_at")
    search_fields = ("fuel_request__trip__order_number",)
    autocomplete_fields = ("fuel_request",)
    readonly_fields = ("uploaded_at",)
