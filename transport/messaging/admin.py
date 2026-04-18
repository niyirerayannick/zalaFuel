from django.contrib import admin

from .models import DriverManagerMessage, FuelRequest, NotificationLog, WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "direction",
        "status",
        "related_trip",
        "twilio_sid",
        "created_at",
    )
    list_filter = ("direction", "status", "created_at")
    search_fields = ("phone_number", "message", "twilio_sid")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "phone_number",
        "user",
        "status",
        "twilio_sid",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("phone_number", "message", "twilio_sid")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"


@admin.register(FuelRequest)
class FuelRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "driver",
        "trip",
        "liters_requested",
        "status",
        "approved_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = (
        "driver__name",
        "trip__order_number",
    )
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("driver", "trip", "approved_by")


@admin.register(DriverManagerMessage)
class DriverManagerMessageAdmin(admin.ModelAdmin):
    list_display = ("driver", "sender", "recipient", "created_at", "read_at")
    search_fields = ("driver__full_name", "sender__full_name", "recipient__full_name", "body")
    list_filter = ("created_at", "read_at")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
