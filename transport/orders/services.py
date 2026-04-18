from io import BytesIO
from pathlib import Path
import warnings

from django.conf import settings
from django.utils import timezone
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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


def _display_value(value, default="-"):
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def build_order_pdf_context(order):
    return {
        "order": order,
        "customer": getattr(order, "customer", None),
        "route": getattr(order, "route", None),
        "generated_at": timezone.now(),
        "quantity": order.display_quantity or "Not set",
        "business_unit": (
            f"{order.formatted_total_quantity} {order.quantity_unit_symbol}".strip()
            if order.quantity_unit_symbol
            else order.formatted_total_quantity
        ) or "Not set",
        "weight": order.formatted_weight_kg or "Not set",
    }


def render_order_pdf(order):
    context = build_order_pdf_context(order)
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
    brand_green = colors.HexColor("#0F5B2A")
    soft_green = colors.HexColor("#EDF8F0")
    ink = colors.HexColor("#0F172A")
    slate = colors.HexColor("#475569")
    border = colors.HexColor("#D8E3DA")

    title_style = ParagraphStyle(
        "OrderPdfTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=brand_green,
        spaceAfter=4,
    )
    subtitle_style = ParagraphStyle(
        "OrderPdfSubtitle",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=slate,
    )
    section_style = ParagraphStyle(
        "OrderPdfSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=brand_green,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "OrderPdfBody",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=13,
        textColor=ink,
    )

    logo_stream = _logo_stream()
    header_left = []
    if logo_stream:
        header_left.append(Image(logo_stream, width=34 * mm, height=16 * mm))
        header_left.append(Spacer(1, 2 * mm))
    header_left.extend(
        [
            Paragraph("ZALA Terminal", title_style),
            Paragraph("Order Summary Document", subtitle_style),
        ]
    )
    header_right = [
        Paragraph(f"<b>Order No</b><br/>{order.order_number}", body_style),
        Spacer(1, 2),
        Paragraph(f"<b>Date</b><br/>{timezone.localtime(context['generated_at']).strftime('%d/%m/%Y %H:%M')}", body_style),
        Spacer(1, 2),
        Paragraph(f"<b>Status</b><br/>{order.get_status_display()}", body_style),
    ]
    header = Table([[header_left, header_right]], colWidths=[118 * mm, 52 * mm])
    header.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("BACKGROUND", (1, 0), (1, 0), soft_green),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    summary = Table(
        [[
            Paragraph(f"<b>Customer</b><br/>{_display_value(getattr(context['customer'], 'company_name', None))}", body_style),
            Paragraph(f"<b>Route</b><br/>{_display_value(getattr(context['route'], 'origin', None))} to {_display_value(getattr(context['route'], 'destination', None))}", body_style),
            Paragraph(f"<b>Quoted Price</b><br/>{order.currency_symbol} {_display_value(order.quoted_price)}", body_style),
        ]],
        colWidths=[56 * mm, 56 * mm, 58 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), soft_green),
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    detail_rows = [
        ["Commodity", order.get_commodity_type_display()],
        ["Description", _display_value(order.commodity_description)],
        ["Operational Quantity", context["quantity"]],
        ["Business Unit", context["business_unit"]],
        ["Weight", context["weight"]],
        ["Pickup Address", _display_value(order.pickup_address)],
        ["Delivery Address", _display_value(order.delivery_address)],
        ["Pickup Contact", _display_value(order.pickup_contact)],
        ["Delivery Contact", _display_value(order.delivery_contact)],
        ["Pickup Date", timezone.localtime(order.requested_pickup_date).strftime("%d/%m/%Y %H:%M")],
        ["Delivery Date", timezone.localtime(order.requested_delivery_date).strftime("%d/%m/%Y %H:%M")],
        ["Payment Terms", order.get_payment_terms_display()],
        ["Special Instructions", _display_value(order.special_instructions)],
    ]
    details = Table(detail_rows, colWidths=[50 * mm, 120 * mm])
    details.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E6EEE8")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F8FBF8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 7 * mm),
        summary,
        Spacer(1, 7 * mm),
        Paragraph("Order Details", section_style),
        details,
    ]
    doc.build(story)
    return buffer.getvalue(), context
