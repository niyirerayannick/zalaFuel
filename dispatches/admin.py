from django.contrib import admin

from .models import Dispatch


@admin.register(Dispatch)
class DispatchAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "dispatch_date", "product", "terminal", "omc", "destination", "quantity_dispatched")
    list_filter = ("dispatch_date", "terminal", "product", "omc")
    search_fields = ("reference_number", "destination", "omc__name", "terminal__name")

