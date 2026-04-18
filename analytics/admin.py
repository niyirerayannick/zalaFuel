from django.contrib import admin

from .models import MarketShareSnapshot


@admin.register(MarketShareSnapshot)
class MarketShareSnapshotAdmin(admin.ModelAdmin):
    list_display = ("snapshot_date", "omc", "product", "volume_liters", "revenue_amount", "market_share_percent")
    list_filter = ("snapshot_date", "product", "omc")
    search_fields = ("omc__name", "product__name")

