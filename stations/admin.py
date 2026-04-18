from django.contrib import admin

from .models import Nozzle, Pump, Station


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location", "manager")
    search_fields = ("name", "code", "location")


@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = ("label", "station", "tank", "is_active", "updated_at")
    list_filter = ("is_active", "station")
    search_fields = ("label", "station__name", "station__code", "tank__name")


@admin.register(Nozzle)
class NozzleAdmin(admin.ModelAdmin):
    list_display = ("pump", "tank", "fuel_type", "meter_start", "meter_end", "is_active")
    list_filter = ("fuel_type", "is_active", "pump__station")
    search_fields = ("pump__label", "pump__station__name", "tank__name")
