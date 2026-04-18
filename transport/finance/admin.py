from django.contrib import admin

from .models import DriverAllowance, DriverFee, Expense, ExpenseType, Payment, Revenue, RevenueType


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("trip", "customer", "amount", "payment_date", "payment_method", "reference")
    list_filter = ("payment_date", "payment_method")
    search_fields = ("trip__order_number", "reference", "customer__company_name")
    autocomplete_fields = ("trip", "customer")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("category", "trip", "vehicle", "amount", "expense_date")
    list_filter = ("category", "expense_date")
    search_fields = ("category", "description", "trip__order_number")
    autocomplete_fields = ("trip", "vehicle")


@admin.register(DriverFee)
class DriverFeeAdmin(admin.ModelAdmin):
    list_display = ("driver", "trip", "amount", "fee_date", "payment_status")
    list_filter = ("payment_status", "fee_date")
    search_fields = ("driver__name", "trip__order_number")
    autocomplete_fields = ("driver", "trip")


@admin.register(ExpenseType)
class ExpenseTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(RevenueType)
class RevenueTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    list_display = ("trip", "type", "amount", "created_by", "created_at")
    list_filter = ("type", "created_at")
    search_fields = ("trip__order_number", "type__name")
    autocomplete_fields = ("trip", "type", "created_by")


@admin.register(DriverAllowance)
class DriverAllowanceAdmin(admin.ModelAdmin):
    list_display = ("driver", "trip", "amount", "status", "approved_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("driver__name", "trip__order_number")
    autocomplete_fields = ("driver", "trip", "approved_by", "created_by")
