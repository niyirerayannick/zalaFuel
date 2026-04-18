from django.contrib import admin

from .models import Alert


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("title", "alert_type", "severity", "status", "terminal", "tank", "triggered_at")
    list_filter = ("alert_type", "severity", "status")
    search_fields = ("title", "message", "terminal__name", "tank__name")
