from django.contrib import admin

from .models import Vehicle, VehicleOwner


@admin.register(VehicleOwner)
class VehicleOwnerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "bank_name", "bank_account", "created_at")
    search_fields = ("name", "phone", "bank_name", "bank_account")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "plate_number",
        "vehicle_type",
        "status",
        "current_odometer",
        "insurance_expiry",
        "inspection_expiry",
        "next_service_km",
    )
    list_filter = ("status", "vehicle_type")
    search_fields = ("plate_number", "vehicle_type")
    autocomplete_fields = ("owner",)
