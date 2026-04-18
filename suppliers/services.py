from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.models import InventoryRecord
from inventory.services import record_tank_stock_delta

from .models import DeliveryReceipt, FuelPurchaseOrder


def post_supplier_delivery(*, receipt_id, actor):
    """
    Validate and post a supplier delivery into the linked tank.
    """
    with transaction.atomic():
        receipt = (
            DeliveryReceipt.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "purchase_order__station",
                "tank",
            )
            .select_for_update()
            .get(pk=receipt_id)
        )

        if receipt.status == DeliveryReceipt.Status.RECEIVED:
            raise ValidationError("This delivery has already been posted.")
        if receipt.status == DeliveryReceipt.Status.CANCELLED:
            raise ValidationError("Cancelled deliveries cannot be posted.")

        receipt.full_clean()
        purchase_order = receipt.purchase_order
        tank = receipt.tank
        if tank is None:
            raise ValidationError({"tank": "Tank is required to receive fuel."})

        previous_quantity = Decimal(tank.current_volume_liters or 0)
        new_quantity = previous_quantity + Decimal(receipt.delivered_volume or 0)
        if tank.capacity_liters and new_quantity > tank.capacity_liters:
            raise ValidationError(
                {
                    "delivered_volume": (
                        f"Tank capacity exceeded. Current stock is {tank.current_volume_liters} L, "
                        f"capacity is {tank.capacity_liters} L, and delivery is {receipt.delivered_volume} L."
                    )
                }
            )

        reference = receipt.delivery_reference or receipt.purchase_order.reference or f"Delivery #{receipt.pk}"
        unit_cost = receipt.unit_cost if receipt.unit_cost is not None else purchase_order.unit_cost
        notes = receipt.notes or f"Supplier receipt posted for PO {purchase_order.reference}."
        record_tank_stock_delta(
            tank,
            receipt.delivered_volume,
            change_type=InventoryRecord.ChangeType.IN,
            movement_type=InventoryRecord.MovementType.DELIVERY,
            reference=reference,
            supplier=purchase_order.supplier,
            delivery_receipt=receipt,
            performed_by=actor,
            unit_cost=unit_cost,
            notes=notes,
        )

        receipt.status = DeliveryReceipt.Status.RECEIVED
        receipt.received_by = actor
        receipt.posted_at = timezone.now()
        receipt.save(update_fields=["status", "received_by", "posted_at", "updated_at"])

        total_received = (
            purchase_order.deliveries.filter(status=DeliveryReceipt.Status.RECEIVED).aggregate(
                total=Sum("delivered_volume")
            )["total"]
            or Decimal("0")
        )
        purchase_order.status = (
            FuelPurchaseOrder.Status.DELIVERED
            if total_received >= Decimal(purchase_order.volume_liters or 0)
            else FuelPurchaseOrder.Status.ORDERED
        )
        purchase_order.save(update_fields=["status", "updated_at"])

        return receipt
