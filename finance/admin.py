from django.contrib import admin

from .models import CustomerAccount, Invoice, Payment, Receipt


@admin.register(CustomerAccount)
class CustomerAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "sales_customer", "contact_person", "phone", "credit_limit", "balance")
    search_fields = ("name", "contact_person", "phone", "email")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "amount", "status", "due_date")
    list_filter = ("status",)
    search_fields = ("reference", "customer__name")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "reference", "created_at")
    list_filter = ("method",)
    search_fields = ("invoice__reference", "reference")


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "payment")
    search_fields = ("receipt_number",)
