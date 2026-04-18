import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from finance.receivable_sync import sync_finance_customer_account_from_sales_customer

from .models import Customer

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Customer)
def mirror_credit_customer_to_finance_account(sender, instance, **kwargs):
    """Keep linked ``CustomerAccount`` aligned when POS customer master data changes."""
    if getattr(instance, "_skip_finance_mirror", False):
        return
    from finance.models import CustomerAccount

    linked = CustomerAccount.objects.filter(sales_customer=instance).exists()
    if not instance.is_credit_allowed and not linked:
        return
    try:
        sync_finance_customer_account_from_sales_customer(instance)
    except Exception:
        logger.exception("Failed to mirror sales.Customer %s to finance CustomerAccount", instance.pk)
