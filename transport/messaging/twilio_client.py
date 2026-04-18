"""
Twilio transport helpers.

Outbound messaging goes through this module so we have a single point
to mock in tests and to swap out the transport layer if needed.
"""

import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client():
    """
    Return a fresh Twilio REST client each time.

    We intentionally do NOT cache the client so that credential changes
    (e.g. updating .env) take effect without restarting the server.
    """
    try:
        from twilio.rest import Client

        account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
        auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
        if not account_sid or not auth_token:
            logger.warning(
                "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN not configured - outbound Twilio messages will not be sent."
            )
            return None
        return Client(account_sid, auth_token)
    except ImportError:
        logger.warning("twilio package not installed - outbound Twilio messages will not be sent.")
        return None


def _normalize_phone(phone: str) -> str:
    """Normalize a phone number to ``+250xxxxxxxxx`` style."""
    phone = (phone or "").strip()
    if not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+250" + phone[1:]
        else:
            phone = "+" + phone
    return phone


def _format_whatsapp(phone: str) -> str:
    """Ensure phone is in ``whatsapp:+250xxxxxxxxx`` format."""
    phone = (phone or "").strip()
    if phone.startswith("whatsapp:"):
        return phone
    return f"whatsapp:{_normalize_phone(phone)}"


def send_whatsapp_message(phone: str, message: str) -> str | None:
    """
    Send a WhatsApp message via Twilio.

    Returns the Twilio message SID on success, or *None* if sending is
    skipped (missing credentials, twilio not installed, etc.).

    The caller is responsible for creating/updating ``WhatsAppMessage``
    and ``NotificationLog`` records.
    """
    from .models import WhatsAppMessage

    formatted_to = _format_whatsapp(phone)
    from_number = _format_whatsapp(getattr(settings, "TWILIO_WHATSAPP_NUMBER", ""))

    msg_record = WhatsAppMessage.objects.create(
        phone_number=phone,
        message=message,
        direction=WhatsAppMessage.Direction.OUTGOING,
        status=WhatsAppMessage.Status.SENT,
    )

    client = _get_client()
    if client is None:
        logger.info("WhatsApp (dry-run) -> %s: %s", phone, message[:120])
        msg_record.status = WhatsAppMessage.Status.FAILED
        msg_record.save(update_fields=["status", "updated_at"])
        return None

    callback_url = getattr(settings, "TWILIO_STATUS_CALLBACK_URL", "")

    try:
        create_kwargs = {
            "body": message,
            "from_": from_number,
            "to": formatted_to,
        }
        if callback_url:
            create_kwargs["status_callback"] = callback_url
        tw_msg = client.messages.create(**create_kwargs)
        msg_record.twilio_sid = tw_msg.sid
        msg_record.status = WhatsAppMessage.Status.SENT
        msg_record.save(update_fields=["twilio_sid", "status", "updated_at"])
        logger.info("WhatsApp sent -> %s SID=%s", phone, tw_msg.sid)
        return tw_msg.sid
    except Exception:
        logger.exception("Failed to send WhatsApp to %s", phone)
        msg_record.status = WhatsAppMessage.Status.FAILED
        msg_record.save(update_fields=["status", "updated_at"])
        return None


def send_sms_message(phone: str, message: str) -> str | None:
    """Send a plain SMS message via Twilio."""
    formatted_to = _normalize_phone(phone)
    from_number = _normalize_phone(getattr(settings, "TWILIO_SMS_NUMBER", ""))
    messaging_service_sid = getattr(settings, "TWILIO_MESSAGING_SERVICE_SID", "")

    client = _get_client()
    if client is None:
        logger.info("SMS (dry-run) -> %s: %s", formatted_to, message[:120])
        return None

    if (not from_number or from_number == "+") and not messaging_service_sid:
        logger.warning(
            "TWILIO_SMS_NUMBER or TWILIO_MESSAGING_SERVICE_SID not configured - SMS will not be sent."
        )
        return None

    try:
        create_kwargs = {"body": message, "to": formatted_to}
        if messaging_service_sid:
            create_kwargs["messaging_service_sid"] = messaging_service_sid
        else:
            create_kwargs["from_"] = from_number
        tw_msg = client.messages.create(**create_kwargs)
        logger.info("SMS sent -> %s SID=%s", formatted_to, tw_msg.sid)
        return tw_msg.sid
    except Exception:
        logger.exception("Failed to send SMS to %s", formatted_to)
        return None
