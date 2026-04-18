from django.contrib import admin

from .models import Terminal, TerminalActivityLog


@admin.register(Terminal)
class TerminalAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location", "manager", "status", "capacity_liters", "is_active")
    list_filter = ("status", "is_active")
    search_fields = ("name", "code", "location", "manager__full_name", "manager__email", "manager_name")


@admin.register(TerminalActivityLog)
class TerminalActivityLogAdmin(admin.ModelAdmin):
    list_display = ("terminal", "action", "event_time")
    search_fields = ("terminal__name", "action", "description")
    list_filter = ("action",)
