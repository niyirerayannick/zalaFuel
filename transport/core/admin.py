from django.contrib import admin

from .models import CommodityType, TransportRate


@admin.register(CommodityType)
class CommodityTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "updated_at")
    list_filter = ("is_active", "code")
    search_fields = ("name", "code")


@admin.register(TransportRate)
class TransportRateAdmin(admin.ModelAdmin):
    list_display = ("route", "commodity_type", "rate_per_km", "minimum_charge", "is_active")
    list_filter = ("commodity_type", "is_active")
    search_fields = ("route__origin", "route__destination")
    autocomplete_fields = ("route", "commodity_type")
