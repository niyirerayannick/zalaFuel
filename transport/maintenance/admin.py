from django.contrib import admin

from .models import MaintenanceRecord


@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "service_type", "service_date", "service_km", "cost", "downtime_days")
    list_filter = ("service_type", "service_date")
    search_fields = ("vehicle__plate_number", "service_type", "workshop")
    autocomplete_fields = ("vehicle",)
