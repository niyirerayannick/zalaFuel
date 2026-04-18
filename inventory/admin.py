from django.contrib import admin

from .models import FuelTank, InventoryRecord, StockReconciliation, TankDipReading


@admin.register(FuelTank)
class FuelTankAdmin(admin.ModelAdmin):
    list_display = ("name", "station", "fuel_type", "capacity_liters", "current_volume_liters")
    list_filter = ("fuel_type", "station")
    search_fields = ("name", "station__name", "station__code")
    readonly_fields = ("current_volume_liters",)


@admin.register(TankDipReading)
class TankDipReadingAdmin(admin.ModelAdmin):
    list_display = ("tank", "reading_time", "volume_liters", "method", "measured_by")
    list_filter = ("method", "tank__station")
    search_fields = ("tank__name", "tank__station__name")


@admin.register(StockReconciliation)
class StockReconciliationAdmin(admin.ModelAdmin):
    list_display = ("tank", "shift", "expected_volume", "actual_volume", "variance", "created_at")
    list_filter = ("tank__station",)
    search_fields = ("tank__name", "shift__id")


@admin.register(InventoryRecord)
class InventoryRecordAdmin(admin.ModelAdmin):
    list_display = ("tank", "movement_type", "change_type", "quantity", "balance_after", "reference", "created_at")
    list_filter = ("movement_type", "change_type", "tank__station")
    search_fields = ("tank__name", "reference")
