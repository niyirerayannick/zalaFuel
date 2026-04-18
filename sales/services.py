from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from accounts.models import SystemSettings
from inventory.models import FuelTank, InventoryRecord
from inventory.services import record_tank_stock_delta
from stations.models import Nozzle

from .models import CreditPayment, CreditTransaction, Customer, FuelSale, ShiftSession


DECIMAL_2 = Decimal("0.01")


def quantize_2(value):
    return Decimal(value or 0).quantize(DECIMAL_2, rounding=ROUND_HALF_UP)


def open_shift_conflicts(*, station, attendant, exclude_shift=None):
    """Return blocking open-shift conflicts for the selected station/attendant."""
    conflicts = {}
    queryset = ShiftSession.objects.filter(status=ShiftSession.Status.OPEN)
    if exclude_shift and exclude_shift.pk:
        queryset = queryset.exclude(pk=exclude_shift.pk)

    station_shift = queryset.filter(station=station).select_related("attendant", "station").first()
    if station_shift:
        conflicts["station"] = f"{station.name} already has open shift #{station_shift.pk}."

    attendant_shift = queryset.filter(attendant=attendant).select_related("station", "attendant").first()
    if attendant_shift:
        conflicts["attendant"] = f"{attendant.full_name} already has open shift #{attendant_shift.pk} at {attendant_shift.station.name}."

    return conflicts


def post_sale_and_update_inventory(
    *,
    shift,
    attendant,
    nozzle_id,
    closing_meter,
    payment_method,
    customer_id=None,
    customer_name="",
    receipt_number="",
):
    """
    Finalize a fuel sale and reduce tank inventory in one atomic transaction.
    """
    if shift is None or shift.status != ShiftSession.Status.OPEN:
        raise ValidationError("An open shift is required to post a sale.")

    with transaction.atomic():
        nozzle = (
            Nozzle.objects.select_related("pump", "pump__station", "tank")
            .select_for_update()
            .get(pk=nozzle_id)
        )
        if nozzle.pump.station_id != shift.station_id:
            raise ValidationError("Selected nozzle does not belong to the active shift station.")
        if not nozzle.tank_id:
            raise ValidationError("Selected nozzle is not linked to a tank.")

        tank = FuelTank.objects.select_for_update().get(pk=nozzle.tank_id)
        if tank.station_id != shift.station_id:
            raise ValidationError("Selected tank does not belong to the active shift station.")
        if tank.fuel_type != nozzle.fuel_type:
            raise ValidationError("Nozzle fuel type must match the linked tank fuel type.")

        latest_sale = (
            FuelSale.objects.select_for_update()
            .filter(nozzle_id=nozzle.pk, closing_meter__isnull=False)
            .order_by("-created_at", "-pk")
            .only("closing_meter")
            .first()
        )
        opening_meter = quantize_2(latest_sale.closing_meter if latest_sale else nozzle.meter_start)
        closing_meter = quantize_2(closing_meter)
        volume = quantize_2(closing_meter - opening_meter)

        if volume <= 0:
            raise ValidationError("Closing meter must be greater than opening meter.")
        if tank.current_volume_liters < volume:
            raise ValidationError(
                f"Insufficient stock. Tank has {tank.current_volume_liters} L available but {volume} L was requested."
            )

        settings = SystemSettings.get_settings()
        unit_price = Decimal("0")
        if settings:
            unit_price = settings.diesel_unit_price if nozzle.fuel_type == Nozzle.FuelType.DIESEL else settings.petrol_unit_price
        unit_price = quantize_2(unit_price)
        if unit_price <= 0:
            raise ValidationError("Unit price must be greater than zero before posting a sale.")

        total_amount = quantize_2(volume * unit_price)
        customer = None
        if payment_method == FuelSale.PaymentMethod.CREDIT:
            if not customer_id:
                raise ValidationError({"customer": "Customer is required for credit sales."})
            customer = Customer.objects.select_for_update().get(pk=customer_id)
            if not customer.is_credit_allowed:
                raise ValidationError({"customer": "This customer is not allowed to buy on credit."})
            projected_balance = quantize_2(customer.current_balance + total_amount)
            if customer.credit_limit and projected_balance > customer.credit_limit:
                raise ValidationError(
                    {
                        "customer": (
                            f"Credit limit exceeded. Current balance is {customer.current_balance} "
                            f"and limit is {customer.credit_limit}."
                        )
                    }
                )

        sale = FuelSale(
            shift=shift,
            attendant=attendant,
            nozzle=nozzle,
            pump=nozzle.pump,
            tank=tank,
            opening_meter=opening_meter,
            closing_meter=closing_meter,
            volume_liters=volume,
            unit_price=unit_price,
            total_amount=total_amount,
            payment_method=payment_method,
            customer_name=customer_name,
            receipt_number=receipt_number,
        )
        sale.full_clean()
        sale.save()

        record_tank_stock_delta(
            tank,
            -volume,
            change_type=InventoryRecord.ChangeType.OUT,
            movement_type=InventoryRecord.MovementType.SALE,
            reference=f"Sale #{sale.pk} - nozzle {nozzle.pk}",
            performed_by=attendant,
            notes=f"Posted fuel sale for shift #{shift.pk}.",
        )

        sale.inventory_posted = True
        sale.inventory_posted_at = timezone.now()
        sale.save(update_fields=["inventory_posted", "inventory_posted_at", "updated_at"])

        if customer:
            customer.current_balance = projected_balance
            customer.save(update_fields=["current_balance", "updated_at"])
            CreditTransaction.objects.create(
                customer=customer,
                sale=sale,
                amount=total_amount,
                amount_paid=Decimal("0"),
            )

        sale.tank = tank
        tank.refresh_from_db(fields=["current_volume_liters", "updated_at"])
        return sale, tank


def shift_sales_summary(shift):
    """Operational sales and reconciliation summary generated from linked sales."""
    sales = FuelSale.objects.filter(shift=shift)
    totals = sales.aggregate(
        total_sales=Sum("total_amount"),
        total_liters=Sum("volume_liters"),
        sales_count=Count("id"),
    )
    payment_rows = list(
        sales.values("payment_method")
        .annotate(total=Sum("total_amount"), liters=Sum("volume_liters"), count=Count("id"))
        .order_by("payment_method")
    )
    fuel_rows = list(
        sales.values("nozzle__fuel_type")
        .annotate(total=Sum("total_amount"), liters=Sum("volume_liters"), count=Count("id"))
        .order_by("nozzle__fuel_type")
    )
    nozzle_rows = list(
        sales.values("nozzle_id", "nozzle__pump__label", "nozzle__fuel_type")
        .annotate(total=Sum("total_amount"), liters=Sum("volume_liters"), count=Count("id"))
        .order_by("nozzle__pump__label", "nozzle__fuel_type")
    )

    payment_labels = dict(FuelSale.PaymentMethod.choices)
    fuel_labels = dict(Nozzle.FuelType.choices)
    payment_totals = {
        row["payment_method"]: row["total"] or Decimal("0")
        for row in payment_rows
    }
    card_total = payment_totals.get(FuelSale.PaymentMethod.CARD, Decimal("0"))
    mobile_total = payment_totals.get(FuelSale.PaymentMethod.MOBILE, Decimal("0"))
    credit_total = payment_totals.get(FuelSale.PaymentMethod.CREDIT, Decimal("0"))
    gross_total = totals["total_sales"] or Decimal("0")

    if shift.status == ShiftSession.Status.CLOSED:
        expected_cash = shift.expected_cash
        declared_cash = shift.closing_cash
        cash_variance = shift.variance_amount
        card_total = shift.closing_card_total
        mobile_total = shift.closing_mobile_total
        credit_total = shift.closing_credit_total
    else:
        expected_cash = payment_totals.get(FuelSale.PaymentMethod.CASH, Decimal("0"))
        declared_cash = shift.closing_cash
        cash_variance = None
        if declared_cash is not None:
            cash_variance = declared_cash - expected_cash

    return {
        "sales_count": totals["sales_count"] or 0,
        "total_liters": totals["total_liters"] or Decimal("0"),
        "total_sales": gross_total,
        "expected_cash": expected_cash,
        "cash_total": expected_cash,
        "credit_total": credit_total,
        "card_total": card_total,
        "mobile_total": mobile_total,
        "declared_cash": declared_cash,
        "declared_amount": declared_cash,
        "variance_amount": cash_variance,
        "cash_variance": cash_variance,
        "variance_status": _variance_status(cash_variance),
        "by_payment_method": [
            {
                **row,
                "label": payment_labels.get(row["payment_method"], row["payment_method"] or "Unknown"),
                "total": row["total"] or Decimal("0"),
                "liters": row["liters"] or Decimal("0"),
            }
            for row in payment_rows
        ],
        "by_fuel_type": [
            {
                **row,
                "label": fuel_labels.get(row["nozzle__fuel_type"], row["nozzle__fuel_type"] or "Unknown"),
                "total": row["total"] or Decimal("0"),
                "liters": row["liters"] or Decimal("0"),
            }
            for row in fuel_rows
        ],
        "by_nozzle": [
            {
                **row,
                "label": f"{row['nozzle__pump__label']} - {fuel_labels.get(row['nozzle__fuel_type'], row['nozzle__fuel_type'])}",
                "total": row["total"] or Decimal("0"),
                "liters": row["liters"] or Decimal("0"),
            }
            for row in nozzle_rows
        ],
    }


def _variance_status(variance):
    if variance is None:
        return "pending"
    if variance == 0:
        return "balanced"
    if variance > 0:
        return "overage"
    return "shortage"


def receive_credit_payment(
    *,
    customer,
    amount,
    method,
    received_by=None,
    reference="",
    notes="",
):
    """Record a customer credit repayment and allocate it oldest-first."""
    payment_amount = quantize_2(amount)
    if payment_amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        if customer.current_balance <= 0:
            raise ValidationError("This customer has no outstanding credit balance.")
        if payment_amount > quantize_2(customer.current_balance):
            raise ValidationError(
                f"Payment amount exceeds outstanding balance of {quantize_2(customer.current_balance)}."
            )

        payment = CreditPayment.objects.create(
            customer=customer,
            amount=payment_amount,
            method=method,
            reference=reference,
            notes=notes,
            received_by=received_by,
        )

        remaining = payment_amount
        transactions = (
            CreditTransaction.objects.select_for_update()
            .filter(customer=customer)
            .exclude(status=CreditTransaction.Status.PAID)
            .order_by("created_at", "pk")
        )
        for entry in transactions:
            if remaining <= 0:
                break
            outstanding = quantize_2(entry.amount) - quantize_2(entry.amount_paid)
            if outstanding <= 0:
                entry.status = CreditTransaction.Status.PAID
                entry.save(update_fields=["status", "updated_at"])
                continue
            allocation = outstanding if outstanding <= remaining else remaining
            entry.amount_paid = quantize_2(entry.amount_paid + allocation)
            remaining = quantize_2(remaining - allocation)
            if entry.amount_paid >= quantize_2(entry.amount):
                entry.status = CreditTransaction.Status.PAID
            elif entry.amount_paid > 0:
                entry.status = CreditTransaction.Status.PARTIAL
            else:
                entry.status = CreditTransaction.Status.UNPAID
            entry.save(update_fields=["amount_paid", "status", "updated_at"])

        customer.current_balance = quantize_2(customer.current_balance - payment_amount)
        customer.save(update_fields=["current_balance", "updated_at"])

        return payment, customer
