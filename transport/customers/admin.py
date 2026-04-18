from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_person", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("company_name", "contact_person", "phone", "email")
