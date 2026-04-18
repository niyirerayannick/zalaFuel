from django.contrib import admin

from .models import RevenueEntry


@admin.register(RevenueEntry)
class RevenueEntryAdmin(admin.ModelAdmin):
    list_display = ("revenue_date", "omc", "product", "terminal", "volume_liters", "amount")
    list_filter = ("revenue_date", "terminal", "product", "omc")
    search_fields = ("omc__name", "product__name", "terminal__name")

