import logging

from .models import NotificationLog
from .twilio_client import send_whatsapp_message

logger = logging.getLogger(__name__)


def send_notification(*, phone_number, message, user=None):
    if not phone_number:
        logger.warning("Skipping notification because no phone number was supplied.")
        return None
    sid = send_whatsapp_message(phone_number, message)
    return NotificationLog.objects.create(
        user=user,
        phone_number=phone_number,
        message=message,
        status=NotificationLog.Status.SENT if sid else NotificationLog.Status.FAILED,
        twilio_sid=sid or "",
    )


def notify_trip_invoice_ready(trip, invoice):
    message = (
        f"ZALA/ECO ENERGY\n\n"
        f"Your invoice {invoice.reference} for shipment {trip.order_number} is ready.\n"
        f"Amount: {invoice.amount}\n"
        f"Route: {trip.route.origin} to {trip.route.destination}"
    )
    return send_notification(phone_number=trip.customer.phone, user=getattr(trip.customer, "user", None), message=message)


def notify_customer_trip_in_transit(trip):
    message = (
        f"ZALA/ECO ENERGY\n\n"
        f"Your order {trip.order_number} is now in transit.\n"
        f"Route: {trip.route.origin} to {trip.route.destination}"
    )
    return send_notification(phone_number=trip.customer.phone, user=getattr(trip.customer, "user", None), message=message)


def notify_customer_delivery_confirmed(trip):
    message = (
        f"ZALA/ECO ENERGY\n\n"
        f"Delivery confirmation: shipment {trip.order_number} has been completed.\n"
        f"Thank you for shipping with ZALA/ECO ENERGY."
    )
    return send_notification(phone_number=trip.customer.phone, user=getattr(trip.customer, "user", None), message=message)


def notify_customer_trip_started(trip):
    return notify_customer_trip_in_transit(trip)


def notify_customer_delivered(trip):
    return notify_customer_delivery_confirmed(trip)


def notify_driver_trip_assigned(trip):
    driver = getattr(trip, "driver", None)
    if not driver or not getattr(driver, "phone", None):
        logger.warning("Skipping driver assignment notification because no driver phone is available.")
        return None
    message = (
        f"ZALA/ECO ENERGY\n\n"
        f"You have been assigned to trip {trip.order_number}.\n"
        f"Route: {trip.route.origin} to {trip.route.destination}\n"
        f"Vehicle: {trip.vehicle}"
    )
    return send_notification(phone_number=driver.phone, user=getattr(driver, "user", None), message=message)
