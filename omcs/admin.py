from django.contrib import admin

from .models import OMC


@admin.register(OMC)
class OMCAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_person", "phone", "is_active")
    search_fields = ("name", "code")
    list_filter = ("is_active",)

