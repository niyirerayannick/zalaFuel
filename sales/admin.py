from django.contrib import admin

from .models import CreditPayment, CreditTransaction, FuelSale, PumpReading, ShiftSession


@admin.register(ShiftSession)
class ShiftSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "station",
        "attendant",
        "shift_type",
        "status",
        "opened_at",
        "closed_at",
        "total_sales",
        "total_liters",
        "variance_amount",
    )
    list_filter = ("status", "shift_type", "station")
    search_fields = ("station__name", "station__code", "attendant__full_name")


@admin.register(PumpReading)
class PumpReadingAdmin(admin.ModelAdmin):
    list_display = ("shift", "nozzle", "opening_reading", "closing_reading")
    list_filter = ("nozzle__pump__station",)
    search_fields = ("shift__id", "nozzle__pump__label", "nozzle__pump__station__name")


@admin.register(FuelSale)
class FuelSaleAdmin(admin.ModelAdmin):
    list_display = (
        "nozzle",
        "shift",
        "attendant",
        "opening_meter",
        "closing_meter",
        "volume_liters",
        "total_amount",
        "payment_method",
        "created_at",
    )
    list_filter = ("payment_method", "nozzle__pump__station")
    search_fields = ("receipt_number", "customer_name", "shift__id", "attendant__full_name")


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ("customer", "sale", "amount", "amount_paid", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("customer__name", "sale__receipt_number", "sale__id")


@admin.register(CreditPayment)
class CreditPaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount", "method", "reference", "received_by", "created_at")
    list_filter = ("method",)
    search_fields = ("customer__name", "reference", "received_by__full_name")
