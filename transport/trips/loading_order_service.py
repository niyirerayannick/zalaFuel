from decimal import Decimal
from io import BytesIO
from pathlib import Path
import warnings

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from PIL import Image as PILImage

from transport.finance.models import DriverAllowance
from transport.orders.models import OrderDocument
from accounts.emailing import send_atms_email


def _format_decimal(value):
    value = value or Decimal("0")
    formatted = format(value, ",.2f")
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    return formatted


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


def _pdf_value(value):
    if value is None or value == "":
        return "-"
    if isinstance(value, Decimal):
        return _format_decimal(value)
    return str(value)


def build_loading_order_context(trip):
    orders = list(trip.related_orders.select_related("customer", "route"))
    primary_order = trip.job or (orders[0] if orders else None)
    customer = trip.customer
    approved_allowance_total = (
        trip.allowances.filter(status=DriverAllowance.Status.APPROVED)
        .aggregate(total=Sum("amount"))
        .get("total")
        or Decimal("0")
    )

    if primary_order:
        payment_terms = primary_order.get_payment_terms_display()
        product = primary_order.get_commodity_type_display()
        quantity = primary_order.formatted_weight_kg or primary_order.quantity
        loading_depot = primary_order.pickup_address or primary_order.origin or trip.route.origin
        destination = primary_order.delivery_address or primary_order.destination or trip.route.destination
        loading_date = primary_order.requested_pickup_date or trip.created_at
        transport_fees = primary_order.quoted_price or trip.gross_profit
    else:
        payment_terms = "30 days"
        product = trip.commodity_type.name
        quantity_unit = getattr(trip, "quantity_unit", "") or "units"
        quantity = f"{_format_decimal(trip.total_load)} {quantity_unit}".strip()
        loading_depot = trip.route.origin
        destination = trip.route.destination
        loading_date = trip.created_at
        transport_fees = trip.gross_profit

    return {
        "trip": trip,
        "customer": customer,
        "orders": orders,
        "primary_order": primary_order,
        "loading_order_date": timezone.localtime(loading_date) if timezone.is_aware(loading_date) else loading_date,
        "transport_fees": transport_fees or Decimal("0"),
        "payment_terms": payment_terms,
        "product": product,
        "quantity": quantity,
        "loading_depot": loading_depot,
        "destination": destination,
        "truck_plates": trip.vehicle.plate_number,
        "driver_names": trip.driver.name,
        "vehicle_ownership_type": trip.vehicle.get_ownership_type_display() if hasattr(trip.vehicle, "get_ownership_type_display") else "Company",
        "vehicle_owner_name": getattr(trip.vehicle.owner, "name", ""),
        "vehicle_owner_phone": getattr(trip.vehicle.owner, "phone", ""),
        "fuel_needed": trip.fuel_issued or Decimal("0"),
        "driver_mileage_allowance": approved_allowance_total,
        "generated_at": timezone.now(),
    }


def render_loading_order_document(trip):
    context = build_loading_order_context(trip)
    return render_to_string("transport/trips/loading_order_document.html", context), context


def render_loading_order_pdf(trip):
    context = build_loading_order_context(trip)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    brand_green = colors.HexColor("#0f5b2a")
    accent_green = colors.HexColor("#1b8f43")
    soft_green = colors.HexColor("#edf8f0")
    ink = colors.HexColor("#0f172a")
    slate = colors.HexColor("#475569")
    border = colors.HexColor("#dbe5dd")

    title_style = ParagraphStyle(
        "LoadingOrderTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        textColor=brand_green,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "LoadingOrderSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=slate,
    )
    section_style = ParagraphStyle(
        "LoadingOrderSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=brand_green,
        spaceAfter=6,
    )
    body_label_style = ParagraphStyle(
        "LoadingOrderLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=ink,
    )
    body_value_style = ParagraphStyle(
        "LoadingOrderValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=ink,
    )
    note_style = ParagraphStyle(
        "LoadingOrderNote",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=slate,
    )

    logo_stream = _logo_stream()
    header_left = []
    if logo_stream:
        header_left.append(Image(logo_stream, width=34 * mm, height=16 * mm))
        header_left.append(Spacer(1, 2 * mm))
    header_left.extend(
        [
            Paragraph("ZALA Terminal", title_style),
            Paragraph("Loading order authorization and dispatch instruction", subtitle_style),
        ]
    )
    header_right = [
        Paragraph("<b>Document</b><br/>Loading Order", body_value_style),
        Spacer(1, 2 * mm),
        Paragraph(
            f"<b>Date</b><br/>{context['loading_order_date'].strftime('%d/%m/%Y')}",
            body_value_style,
        ),
        Spacer(1, 2 * mm),
        Paragraph(f"<b>Trip Ref</b><br/>{trip.order_number}", body_value_style),
    ]

    header_table = Table(
        [[header_left, header_right]],
        colWidths=[122 * mm, 48 * mm],
    )
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (1, 0), (1, 0), soft_green),
            ]
        )
    )

    summary_table = Table(
        [[
            Paragraph("<b>Client</b><br/>" + _pdf_value(context["customer"].company_name), body_value_style),
            Paragraph("<b>Product</b><br/>" + _pdf_value(context["product"]), body_value_style),
            Paragraph("<b>Destination</b><br/>" + _pdf_value(context["destination"]), body_value_style),
        ]],
        colWidths=[56 * mm, 56 * mm, 56 * mm],
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), soft_green),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#b9dcc3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story = [header_table, Spacer(1, 7 * mm), summary_table, Spacer(1, 7 * mm), Paragraph("Dispatch Details", section_style)]

    rows = [
        [
            Paragraph("1. Client", body_label_style),
            Paragraph(_pdf_value(context["customer"].company_name), body_value_style),
        ],
        [
            Paragraph("2. Transport Fees", body_label_style),
            Paragraph(f"{_format_decimal(context['transport_fees'])} USD", body_value_style),
        ],
        [
            Paragraph("3. Payment Terms", body_label_style),
            Paragraph(_pdf_value(context["payment_terms"]), body_value_style),
        ],
        [
            Paragraph("4. Product", body_label_style),
            Paragraph(_pdf_value(context["product"]), body_value_style),
        ],
        [
            Paragraph("5. Quantity", body_label_style),
            Paragraph(_pdf_value(context["quantity"]), body_value_style),
        ],
        [
            Paragraph("6. Loading Depot", body_label_style),
            Paragraph(_pdf_value(context["loading_depot"]), body_value_style),
        ],
        [
            Paragraph("7. Destination", body_label_style),
            Paragraph(_pdf_value(context["destination"]), body_value_style),
        ],
        [
            Paragraph("8. Truck Plates", body_label_style),
            Paragraph(_pdf_value(context["truck_plates"]), body_value_style),
        ],
        [
            Paragraph("9. Driver Names", body_label_style),
            Paragraph(_pdf_value(context["driver_names"]), body_value_style),
        ],
        [
            Paragraph("10. Vehicle Ownership", body_label_style),
            Paragraph(
                _pdf_value(
                    context["vehicle_owner_name"]
                    if context["vehicle_ownership_type"] == "External" and context["vehicle_owner_name"]
                    else context["vehicle_ownership_type"]
                ),
                body_value_style,
            ),
        ],
        [
            Paragraph("11. Fuel Needed", body_label_style),
            Paragraph(f"{_format_decimal(context['fuel_needed'])} L", body_value_style),
        ],
        [
            Paragraph("12. Driver Mileage Allowance", body_label_style),
            Paragraph(f"{_format_decimal(context['driver_mileage_allowance'])} FRW", body_value_style),
        ],
    ]
    table = Table(rows, colWidths=[58 * mm, 112 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e6efe8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f7fbf8")),
                ("ROWBACKGROUNDS", (1, 0), (1, -1), [colors.white, colors.HexColor("#fbfdfb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))

    footer_note = Table(
        [[
            Paragraph(
                "This loading order was generated by ZALA Terminal and confirms the dispatch details prepared for client execution.",
                note_style,
            ),
            Paragraph(
                f"Generated on {context['generated_at'].strftime('%d/%m/%Y %H:%M')}",
                note_style,
            ),
        ]],
        colWidths=[118 * mm, 52 * mm],
    )
    footer_note.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(footer_note)
    doc.build(story)
    return buffer.getvalue(), context


def generate_loading_order_document(trip, *, created_by=None):
    document_pdf, context = render_loading_order_pdf(trip)
    primary_order = context["primary_order"]
    if primary_order is None:
        return None, context

    filename = f"loading_order_{trip.order_number}.pdf"
    existing = primary_order.documents.filter(document_type="other", name__icontains=trip.order_number).first()
    if existing:
        existing.file.save(filename, ContentFile(document_pdf), save=True)
        return existing, context

    document = OrderDocument.objects.create(
        order=primary_order,
        name=f"Loading Order {trip.order_number}",
        document_type="other",
        uploaded_by=created_by,
    )
    document.file.save(filename, ContentFile(document_pdf), save=True)
    return document, context


def send_loading_order_email(trip, *, created_by=None):
    document, context = generate_loading_order_document(trip, created_by=created_by)
    recipient = context["customer"].email
    if not recipient:
        raise ValueError("Customer email is missing.")

    subject = f"Loading Order - {trip.order_number}"
    email = send_atms_email(
        subject=subject,
        to=[recipient],
        greeting=f"Hello {context['customer'].company_name}",
        headline="Loading Order Ready",
        intro="Please find attached the loading order prepared for your transport service.",
        details=[
            {"label": "Trip Reference", "value": trip.order_number},
            {"label": "Product", "value": context["product"]},
            {"label": "Destination", "value": context["destination"]},
            {"label": "Transport Fees", "value": f"{_format_decimal(context['transport_fees'])} USD"},
        ],
        note="Review the attached loading order document and contact ZALA Terminal if any dispatch detail needs adjustment.",
    )
    pdf_attachment, _ = render_loading_order_pdf(trip)
    email.attach(f"loading_order_{trip.order_number}.pdf", pdf_attachment, "application/pdf")
    email.send(fail_silently=False)
    return document, context
