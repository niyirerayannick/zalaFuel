from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from urllib.parse import urlencode
import warnings

from django.conf import settings
from django.core import signing
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone
from PIL import Image as PILImage
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from accounts.currency import CURRENCY_DECIMALS, CURRENCY_SYMBOLS
from accounts.models import SystemSettings
from .models import DriverAllowance, Expense, ExpenseType, Payment
from transport.orders.models import OrderDocument
from accounts.emailing import send_atms_email


AFRILOTT_GREEN = colors.HexColor("#0F5B2A")
AFRILOTT_LIGHT = colors.HexColor("#EAF7EF")


def _system_currency_context(system_settings=None):
    currency_code = getattr(settings, "DEFAULT_CURRENCY", "USD")
    currency_symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    if system_settings:
        currency_code = system_settings.currency or currency_code
        currency_symbol = system_settings.currency_symbol or CURRENCY_SYMBOLS.get(currency_code, currency_code)
    return currency_code, currency_symbol


def _format_system_currency(amount, currency_code, currency_symbol):
    decimals = CURRENCY_DECIMALS.get(currency_code, 2)
    quant = Decimal("1") if decimals == 0 else Decimal(10) ** -decimals
    value = Decimal(str(amount or 0)).quantize(quant, rounding=ROUND_HALF_UP)
    formatted_value = f"{int(value):,}" if decimals == 0 else f"{value:,.{decimals}f}"
    return f"{currency_symbol} {formatted_value}"


def _system_currency_accounts(system_settings, currency_code):
    account_map = {
        "USD": {
            "currency": "USD",
            "bank_name": getattr(system_settings, "usd_bank_name", ""),
            "account_name": getattr(system_settings, "usd_account_name", ""),
            "account_number": getattr(system_settings, "usd_account_number", ""),
        },
        "RWF": {
            "currency": "RWF",
            "bank_name": getattr(system_settings, "rwf_bank_name", ""),
            "account_name": getattr(system_settings, "rwf_account_name", ""),
            "account_number": getattr(system_settings, "rwf_account_number", ""),
        },
    }
    preferred_account = account_map.get(currency_code)
    if preferred_account:
        return [preferred_account]
    return [account for account in account_map.values() if account["bank_name"] or account["account_name"] or account["account_number"]]


def _logo_path():
    candidate = Path(settings.BASE_DIR) / "static" / "img" / "ZALA Terminal.png"
    return candidate if candidate.exists() else None


def _logo_stream(max_width=900):
    logo = _logo_path()
    if not logo:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PILImage.DecompressionBombWarning)
        img = PILImage.open(logo)
        img.load()
    with img:
        img.thumbnail((max_width, max_width))
        stream = BytesIO()
        img.save(stream, format="PNG", optimize=True)
        stream.seek(0)
        return stream


def _invoice_filename(payment):
    reference = (payment.reference or f"invoice_{payment.pk}").replace("/", "_").replace("\\", "_").replace(" ", "_")
    return f"{reference}.pdf"


def _signed_invoice_payload(payment):
    payload = {
        "p": payment.pk,
        "r": payment.reference or f"INV-{payment.pk}",
        "a": str(payment.amount or Decimal("0")),
        "d": payment.payment_date.isoformat() if payment.payment_date else "",
    }
    return signing.dumps(payload, salt="atms.invoice")


def _invoice_verification_url(payment):
    base_url = getattr(settings, "ATMS_PUBLIC_BASE_URL", "").rstrip("/") or "http://127.0.0.1:8000"
    token = _signed_invoice_payload(payment)
    return f"{base_url}/transport/finance/payments/{payment.pk}/verify/?{urlencode({'token': token})}"


def _invoice_qr_drawing(payment, size=40 * mm):
    widget = qr.QrCodeWidget(_invoice_verification_url(payment), barLevel="M", barBorder=4)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(widget)
    return drawing


def build_invoice_context(payment):
    order = payment.order
    trip = payment.trip
    customer = payment.customer or getattr(order, "customer", None) or getattr(trip, "customer", None)
    route = getattr(trip, "route", None) or getattr(order, "route", None)
    system_settings = SystemSettings.get_settings()
    currency_code, currency_symbol = _system_currency_context(system_settings)
    payment_accounts = _system_currency_accounts(system_settings, currency_code)
    transport_fee = payment.amount or Decimal("0")

    return {
        "payment": payment,
        "order": order,
        "trip": trip,
        "customer": customer,
        "route": route,
        "system_settings": system_settings,
        "company_name": getattr(system_settings, "company_name", "ZALA Terminal"),
        "invoice_reference": payment.reference or f"INV-{payment.pk}",
        "invoice_date": payment.payment_date or timezone.now().date(),
        "payment_terms": order.get_payment_terms_display() if order and getattr(order, "payment_terms", None) else "Due on receipt",
        "commodity": order.get_commodity_type_display() if order and getattr(order, "commodity_type", None) else "Transport Service",
        "quantity": getattr(order, "quantity", "") or (f"{trip.total_load} {trip.quantity_unit}".strip() if trip else "-"),
        "origin": getattr(route, "origin", "") or getattr(order, "origin", "") or "-",
        "destination": getattr(route, "destination", "") or getattr(order, "destination", "") or "-",
        "transport_fee": transport_fee,
        "currency": currency_code,
        "currency_symbol": currency_symbol,
        "transport_fee_display": _format_system_currency(transport_fee, currency_code, currency_symbol),
        "payment_accounts": payment_accounts,
        "generated_at": timezone.now(),
        "verification_code": _signed_invoice_payload(payment),
        "verification_url": _invoice_verification_url(payment),
    }


def render_invoice_pdf(payment):
    context = build_invoice_context(payment)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("InvoiceTitle", parent=styles["Title"], textColor=AFRILOTT_GREEN, fontSize=20)
    subtitle_style = ParagraphStyle("InvoiceSubtitle", parent=styles["Normal"], textColor=colors.HexColor("#0F172A"), fontSize=10, leading=13)
    note_style = ParagraphStyle("InvoiceNote", parent=styles["Normal"], textColor=colors.HexColor("#475569"), fontSize=9)
    verify_style = ParagraphStyle("InvoiceVerify", parent=styles["Normal"], textColor=colors.HexColor("#334155"), fontSize=8, leading=11)
    section_style = ParagraphStyle("InvoiceSection", parent=styles["Heading4"], textColor=AFRILOTT_GREEN, fontSize=11, spaceAfter=4)
    small_style = ParagraphStyle("InvoiceSmall", parent=styles["Normal"], textColor=colors.HexColor("#475569"), fontSize=8, leading=11)

    logo_stream = _logo_stream()
    header_left = []
    if logo_stream:
        header_left.append(Image(logo_stream, width=34 * mm, height=16 * mm))
        header_left.append(Spacer(1, 2 * mm))
    header_left.extend(
        [
            Paragraph(f"{context['company_name']} Transport Invoice", title_style),
            Paragraph("Official billing document for transport services.", subtitle_style),
        ]
    )
    header_right = [
        Paragraph(f"<b>Invoice No</b><br/>{context['invoice_reference']}", subtitle_style),
        Spacer(1, 2),
        Paragraph(f"<b>Invoice Date</b><br/>{context['invoice_date'].strftime('%d/%m/%Y')}", subtitle_style),
        Spacer(1, 2),
        Paragraph(f"<b>Status</b><br/>{payment.get_status_display()}", subtitle_style),
    ]
    header = Table([[header_left, header_right]], colWidths=[112 * mm, 58 * mm])
    header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D1E7D7")),
                ("BACKGROUND", (1, 0), (1, 0), AFRILOTT_LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )

    customer_name = getattr(context["customer"], "company_name", "Customer")
    billing_rows = [
        ["Bill To", customer_name],
        ["Order", getattr(context["order"], "order_number", "-") or "-"],
        ["Trip", getattr(context["trip"], "order_number", "-") or "-"],
        ["Route", f"{context['origin']} to {context['destination']}"],
    ]
    service_rows = [
        ["Commodity", context["commodity"]],
        ["Quantity", context["quantity"]],
        ["Payment Terms", context["payment_terms"]],
        ["Currency", context["currency"]],
    ]
    billing_details = Table(billing_rows, colWidths=[28 * mm, 57 * mm])
    service_details = Table(service_rows, colWidths=[32 * mm, 53 * mm])
    for table in (billing_details, service_details):
        table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D1D5DB")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                    ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FAFC")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
    details = Table(
        [[
            [Paragraph("Billing Details", section_style), billing_details],
            [Paragraph("Service Details", section_style), service_details],
        ]],
        colWidths=[85 * mm, 85 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    total_box = Table([["Total Due", context["transport_fee_display"]]], colWidths=[110 * mm, 60 * mm])
    total_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), AFRILOTT_LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.8, AFRILOTT_GREEN),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("TEXTCOLOR", (1, 0), (1, 0), AFRILOTT_GREEN),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )

    payment_rows = [["Currency", "Bank", "Account Name", "Account Number"]]
    has_payment_info = False
    for account in context["payment_accounts"]:
        bank_name = account["bank_name"] or "-"
        account_name = account["account_name"] or "-"
        account_number = account["account_number"] or "-"
        if account["bank_name"] or account["account_name"] or account["account_number"]:
            has_payment_info = True
        payment_rows.append([account["currency"], bank_name, account_name, account_number])
    payment_table = Table(payment_rows, colWidths=[20 * mm, 48 * mm, 52 * mm, 50 * mm], repeatRows=1)
    payment_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), AFRILOTT_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D1D5DB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, AFRILOTT_LIGHT]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    payment_info_block = [
        Paragraph("Payment Information", section_style),
        payment_table,
    ]
    if not has_payment_info:
        payment_info_block.append(Spacer(1, 2 * mm))
        payment_info_block.append(Paragraph("Payment account details can be configured in System Settings.", small_style))

    verification_block = Table(
        [
            [Paragraph("<b>Authenticity QR</b>", styles["Normal"])],
            [_invoice_qr_drawing(payment, size=44 * mm)],
            [Paragraph("Scan this QR code to open the ZALA Terminal invoice verification page.", verify_style)],
        ],
        colWidths=[170 * mm],
    )
    verification_block.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 8 * mm),
        details,
        Spacer(1, 6 * mm),
        total_box,
        Spacer(1, 6 * mm),
        *payment_info_block,
        Spacer(1, 5 * mm),
        verification_block,
        Spacer(1, 4 * mm),
        Paragraph("Generated by ZALA Terminal.", note_style),
    ]
    doc.build(story)
    return buffer.getvalue(), context


def generate_invoice_document(payment, *, created_by=None):
    if not payment.order_id:
        return None, build_invoice_context(payment)

    pdf_bytes, context = render_invoice_pdf(payment)
    filename = _invoice_filename(payment)
    existing = payment.order.documents.filter(document_type="invoice", name__icontains=(payment.reference or str(payment.pk))).first()
    if existing:
        existing.file.save(filename, ContentFile(pdf_bytes), save=True)
        return existing, context

    document = OrderDocument.objects.create(
        order=payment.order,
        name=f"Invoice {payment.reference or payment.pk}",
        document_type="invoice",
        uploaded_by=created_by,
    )
    document.file.save(filename, ContentFile(pdf_bytes), save=True)
    return document, context


def send_invoice_email(payment, *, created_by=None):
    document, context = generate_invoice_document(payment, created_by=created_by)
    customer = context["customer"]
    recipient = getattr(customer, "email", "")
    if not recipient:
        raise ValueError("Customer email is missing.")

    pdf_bytes, context = render_invoice_pdf(payment)
    email = send_atms_email(
        subject=f"Invoice {context['invoice_reference']}",
        to=[recipient],
        greeting=f"Hello {getattr(customer, 'company_name', 'Customer')}",
        headline="Invoice Issued",
        intro="Your transport invoice has been generated and is attached to this message.",
        details=[
            {"label": "Invoice Reference", "value": context["invoice_reference"]},
            {"label": "Trip Reference", "value": getattr(context["trip"], "order_number", "-")},
            {"label": "Payment Terms", "value": context["payment_terms"]},
            {"label": "Amount Due", "value": context["transport_fee_display"]},
        ],
        note="Please review the attached invoice and arrange payment according to the agreed terms.",
    )
    email.attach(_invoice_filename(payment), pdf_bytes, "application/pdf")
    email.send(fail_silently=False)
    return document, context


def generate_and_send_invoices_for_trip(trip, *, created_by=None):
    invoices = generate_invoices_for_trip(trip)
    sent = []
    for invoice in invoices:
        send_invoice_email(invoice, created_by=created_by)
        sent.append(invoice)
    return sent


def trip_total_expenses(trip):
    return trip.expenses.aggregate(total=Sum("amount")).get("total") or Decimal("0")


def trip_total_revenue(trip):
    revenue_total = trip.revenues.aggregate(total=Sum("amount")).get("total")
    if revenue_total is not None:
        return revenue_total
    return trip.revenue or Decimal("0")


def cost_per_km(trip):
    if not trip.distance:
        return Decimal("0")
    return trip.total_expenses / trip.distance


def outstanding_balance_for_order(order):
    return order.outstanding_balance


def create_trip_expense(*, trip, expense_type_name, amount, description="", created_by=None, vehicle=None):
    expense_type, _ = ExpenseType.objects.get_or_create(name=expense_type_name)
    return Expense.objects.create(
        trip=trip,
        vehicle=vehicle or trip.vehicle,
        type=expense_type,
        category=expense_type.name,
        amount=amount,
        description=description,
        expense_date=timezone.now().date(),
        created_by=created_by,
    )


def sync_trip_rental_expense(*, trip, created_by=None):
    if not getattr(trip, "vehicle_id", None):
        return None

    expense_type, _ = ExpenseType.objects.get_or_create(name="Vehicle Rent")
    existing = Expense.objects.filter(
        trip=trip,
        type=expense_type,
        description="Vehicle rental fee",
    ).first()

    is_external = trip.vehicle.ownership_type == trip.vehicle.OwnershipType.EXTERNAL
    rental_fee = trip.rental_fee or Decimal("0")

    if not is_external or rental_fee <= 0:
        if existing:
            existing.delete()
        return None

    if existing:
        existing.vehicle = trip.vehicle
        existing.amount = rental_fee
        existing.status = Expense.Status.PENDING
        existing.category = expense_type.name
        if created_by and not existing.created_by_id:
            existing.created_by = created_by
        existing.save(update_fields=["vehicle", "amount", "status", "category", "created_by", "updated_at"])
        return existing

    return Expense.objects.create(
        trip=trip,
        vehicle=trip.vehicle,
        type=expense_type,
        category=expense_type.name,
        status=Expense.Status.PENDING,
        amount=rental_fee,
        description="Vehicle rental fee",
        expense_date=timezone.now().date(),
        created_by=created_by,
    )


def approve_allowance(allowance, approver):
    if allowance.status != DriverAllowance.Status.PENDING:
        return allowance
    allowance.status = DriverAllowance.Status.APPROVED
    allowance.approved_by = approver
    allowance.save(update_fields=["status", "approved_by", "updated_at"])
    create_trip_expense(
        trip=allowance.trip,
        expense_type_name="Driver Allowance",
        amount=allowance.amount,
        description=f"Approved allowance for {allowance.driver.name}",
        created_by=approver,
        vehicle=allowance.trip.vehicle,
    )
    return allowance


def generate_invoice_for_trip(trip):
    invoices = generate_invoices_for_trip(trip)
    return invoices[0] if invoices else None


def generate_invoices_for_trip(trip):
    invoices = []
    if not trip.pk:
        return invoices

    grouped_quantities = {}
    for shipment in trip.shipments.select_related("order", "customer"):
        grouped_quantities[shipment.order] = grouped_quantities.get(shipment.order, Decimal("0")) + shipment.quantity

    if not grouped_quantities and trip.job_id and trip.job:
        grouped_quantities[trip.job] = trip.quantity or Decimal("0")

    for order, trip_quantity in grouped_quantities.items():
        total_quantity = order.total_quantity_value
        if total_quantity > 0:
            amount = (order.quoted_price * trip_quantity) / total_quantity
        else:
            amount = order.quoted_price or Decimal("0")

        existing_invoice = Payment.objects.filter(order=order, trip=trip).first()
        legacy_invoice = (
            Payment.objects.filter(
                order=order,
                trip__isnull=True,
                notes__icontains="Auto-generated from trip workflow.",
            )
            .order_by("-created_at")
            .first()
        )
        defaults = {
            "customer": order.customer,
            "amount": amount,
            "payment_date": timezone.now().date(),
            "status": Payment.Status.PENDING,
            "reference": f"INV-{order.order_number}-{trip.order_number}",
            "notes": "Auto-generated from trip workflow.",
        }

        if existing_invoice and legacy_invoice and existing_invoice.pk != legacy_invoice.pk:
            preferred_invoice = legacy_invoice if legacy_invoice.status in {Payment.Status.PAID, Payment.Status.PARTIAL} else existing_invoice
            duplicate_invoice = existing_invoice if preferred_invoice is legacy_invoice else legacy_invoice

            preferred_invoice.trip = trip
            preferred_invoice.customer = order.customer
            preferred_invoice.amount = amount
            preferred_invoice.payment_date = defaults["payment_date"]
            preferred_invoice.reference = defaults["reference"]
            preferred_invoice.notes = defaults["notes"]
            if preferred_invoice.status in {Payment.Status.PENDING, Payment.Status.FAILED}:
                preferred_invoice.status = defaults["status"]
            preferred_invoice.save(
                update_fields=["trip", "customer", "amount", "payment_date", "status", "reference", "notes", "updated_at"]
            )

            if duplicate_invoice.status in {Payment.Status.PENDING, Payment.Status.FAILED}:
                duplicate_invoice.delete()

            invoices.append(preferred_invoice)
            continue

        if not existing_invoice and legacy_invoice:
            existing_invoice = legacy_invoice

        if existing_invoice:
            existing_invoice.trip = trip
            if existing_invoice.status in {Payment.Status.PENDING, Payment.Status.FAILED}:
                for field, value in defaults.items():
                    setattr(existing_invoice, field, value)
                existing_invoice.save(update_fields=["trip", "customer", "amount", "payment_date", "status", "reference", "notes", "updated_at"])
            else:
                existing_invoice.reference = defaults["reference"]
                existing_invoice.notes = defaults["notes"]
                existing_invoice.customer = order.customer
                existing_invoice.save(update_fields=["trip", "customer", "reference", "notes", "updated_at"])
            invoices.append(existing_invoice)
            continue

        invoices.append(Payment.objects.create(order=order, trip=trip, **defaults))

    return invoices
