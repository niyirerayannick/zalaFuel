"""
Bridge POS credit (``sales.Customer``) with finance receivables (``CustomerAccount``).

POS remains the source of truth for pump-side credit balance updates. This module
mirrors that balance onto a linked ``CustomerAccount`` so invoices and payments
can use the same AR record without a full domain merge.
"""

from __future__ import annotations

import logging
import uuid

from django.db import transaction

logger = logging.getLogger(__name__)


def sync_finance_customer_account_from_sales_customer(sales_customer) -> None:
    """
    Upsert a ``CustomerAccount`` linked to ``sales_customer`` and align balances.

    Safe to call after each credit sale; no-ops if the customer is missing.
    """
    if sales_customer is None:
        return

    from sales.models import Customer

    if not isinstance(sales_customer, Customer):
        return

    from .models import CustomerAccount

    with transaction.atomic():
        account = CustomerAccount.objects.select_for_update().filter(sales_customer=sales_customer).first()
        if account:
            account.name = sales_customer.name
            account.phone = sales_customer.phone or ""
            account.email = sales_customer.email or ""
            account.credit_limit = sales_customer.credit_limit
            account.balance = sales_customer.current_balance
            account.save(
                update_fields=["name", "phone", "email", "credit_limit", "balance", "updated_at"]
            )
            return

        reference = f"AR-SC-{sales_customer.pk}-{uuid.uuid4().hex[:10].upper()}"
        CustomerAccount.objects.create(
            sales_customer=sales_customer,
            name=sales_customer.name,
            phone=sales_customer.phone or "",
            email=sales_customer.email or "",
            credit_limit=sales_customer.credit_limit,
            balance=sales_customer.current_balance,
            reference=reference,
        )
