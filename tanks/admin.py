from django.contrib import admin

from .models import Tank, TankStockEntry


@admin.register(Tank)
class TankAdmin(admin.ModelAdmin):
    list_display = ("name", "terminal", "product", "capacity_liters", "current_stock_liters", "minimum_threshold", "is_active")
    list_filter = ("terminal", "product", "is_active")
    search_fields = ("name", "code", "terminal__name")


@admin.register(TankStockEntry)
class TankStockEntryAdmin(admin.ModelAdmin):
    list_display = ("tank", "entry_date", "opening_stock", "stock_in", "stock_out", "closing_stock", "variance")
    list_filter = ("entry_date", "tank__terminal")
    search_fields = ("tank__name", "tank__terminal__name")

