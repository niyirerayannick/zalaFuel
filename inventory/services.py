"""
Central tank stock movements. All physical stock changes should go through these helpers
so ledger rows and balances stay consistent.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from .models import FuelTank, InventoryRecord


def record_tank_stock_delta(
    tank: FuelTank,
    delta_liters: Decimal,
    *,
    change_type: str,
    movement_type: str,
    reference: str = "",
    supplier=None,
    delivery_receipt=None,
    performed_by=None,
    unit_cost=None,
    notes: str = "",
) -> Decimal:
    """
    Apply a signed liter delta to ``tank`` and append one ``InventoryRecord``.

    Positive ``delta_liters`` increases stock; negative decreases (e.g. sales).
    """
    return tank.adjust_stock(
        delta_liters,
        reference=reference,
        change_type=change_type,
        movement_type=movement_type,
        supplier=supplier,
        delivery_receipt=delivery_receipt,
        performed_by=performed_by,
        unit_cost=unit_cost,
        notes=notes or "",
    )


def assert_non_negative_delta_for_sale(volume_liters: Decimal) -> None:
    if volume_liters <= 0:
        raise ValidationError("Sale volume must be greater than zero.")
