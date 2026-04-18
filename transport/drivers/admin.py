from django.contrib import admin

from .models import Driver


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "license_number", "license_category", "work_status", "license_expiry", "status")
    list_filter = ("status", "work_status", "license_category")
    search_fields = ("name", "phone", "license_number")
