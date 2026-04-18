from django.contrib import admin

from .models import Route


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("origin", "destination", "distance_km", "is_active")
    list_filter = ("is_active",)
    search_fields = ("origin", "destination")
