"""
Webhook views for Twilio WhatsApp integration.
"""

import hashlib
import hmac
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .commands import parse_and_execute
from .models import WhatsAppMessage
from .twilio_client import send_whatsapp_message

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Twilio request validation
# ---------------------------------------------------------------------------

def _validate_twilio_request(request) -> bool:
    """
    Validate that an incoming request genuinely comes from Twilio.

    Uses the X-Twilio-Signature header and the TWILIO_AUTH_TOKEN to
    verify the request.  In DEBUG mode validation is skipped because
    ngrok rewrites the Host header, causing URL-based HMAC to fail.
    """
    # In development (behind ngrok) the URL Django sees is localhost,
    # but Twilio signs against the public ngrok URL → always mismatches.
    # Skip validation in DEBUG; enforce in production.
    if settings.DEBUG:
        logger.debug("DEBUG mode – skipping Twilio signature validation.")
        return True

    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set – rejecting webhook request.")
        return False

    signature = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
    if not signature:
        logger.warning("No X-Twilio-Signature header present.")
        return False

    # Build the URL Twilio used to sign the request.
    # Behind a reverse proxy (Coolify/Traefik) Django may see http://
    # while Twilio signed https://.  Use build_absolute_uri() which
    # respects SECURE_PROXY_SSL_HEADER + USE_X_FORWARDED_HOST.
    url = request.build_absolute_uri()
    logger.debug("Twilio validation URL: %s", url)

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(auth_token)
        valid = validator.validate(url, request.POST.dict(), signature)
        if not valid:
            logger.warning(
                "Twilio signature mismatch. URL used: %s | Signature: %s",
                url, signature[:20] + "...",
            )
        return valid
    except ImportError:
        # Fallback: manual HMAC validation
        params = request.POST.dict()
        data = url + urlencode(sorted(params.items()))
        expected = hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64

        expected_b64 = base64.b64encode(expected).decode("utf-8")
        return hmac.compare_digest(expected_b64, signature)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """
    POST /api/whatsapp/webhook/

    Receives incoming WhatsApp messages from Twilio, logs them, and
    dispatches to the command parser.  Returns TwiML-free plain-text
    response (Twilio will deliver our reply via the REST API instead).
    """
    # Validate Twilio signature
    if not _validate_twilio_request(request):
        logger.warning("Invalid Twilio signature from %s", request.META.get("REMOTE_ADDR"))
        return HttpResponseForbidden("Invalid signature")

    from_number = request.POST.get("From", "").replace("whatsapp:", "").strip()
    body = request.POST.get("Body", "").strip()
    twilio_sid = request.POST.get("MessageSid", "")

    logger.info("WhatsApp incoming from %s: %s", from_number, body[:100])

    # Log inbound message
    WhatsAppMessage.objects.create(
        phone_number=from_number,
        message=body,
        direction=WhatsAppMessage.Direction.INCOMING,
        status=WhatsAppMessage.Status.RECEIVED,
        twilio_sid=twilio_sid,
    )

    # Parse command and get reply
    reply = parse_and_execute(from_number, body)

    # Send reply via REST API (not TwiML) so we control delivery ourselves
    if reply:
        send_whatsapp_message(from_number, reply)

    # Return empty 200 (Twilio doesn't need TwiML when we send via REST)
    return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# Status callback endpoint
# ---------------------------------------------------------------------------

# Map Twilio status strings → our model choices
_TWILIO_STATUS_MAP = {
    "queued": WhatsAppMessage.Status.SENT,
    "sent": WhatsAppMessage.Status.SENT,
    "delivered": WhatsAppMessage.Status.DELIVERED,
    "read": WhatsAppMessage.Status.READ,
    "failed": WhatsAppMessage.Status.FAILED,
    "undelivered": WhatsAppMessage.Status.FAILED,
}


@csrf_exempt
@require_POST
def whatsapp_status_callback(request):
    """
    POST /api/whatsapp/status/

    Twilio calls this URL whenever an outgoing message's delivery status
    changes (queued → sent → delivered → read, or failed/undelivered).

    Configure this as the **Status Callback URL** in your Twilio console
    or pass it via the ``status_callback`` parameter when sending.
    """
    if not _validate_twilio_request(request):
        logger.warning("Invalid Twilio signature on status callback from %s", request.META.get("REMOTE_ADDR"))
        return HttpResponseForbidden("Invalid signature")

    message_sid = request.POST.get("MessageSid", "")
    message_status = request.POST.get("MessageStatus", "").lower()
    to_number = request.POST.get("To", "").replace("whatsapp:", "").strip()
    error_code = request.POST.get("ErrorCode", "")
    error_message = request.POST.get("ErrorMessage", "")

    logger.info(
        "WhatsApp status callback: SID=%s status=%s to=%s",
        message_sid, message_status, to_number,
    )

    new_status = _TWILIO_STATUS_MAP.get(message_status)
    if not new_status:
        logger.warning("Unknown Twilio status: %s", message_status)
        return HttpResponse(status=200)

    # Update WhatsAppMessage record
    updated = WhatsAppMessage.objects.filter(
        twilio_sid=message_sid,
        direction=WhatsAppMessage.Direction.OUTGOING,
    ).update(status=new_status)

    if updated:
        logger.info("Updated %d message(s) SID=%s → %s", updated, message_sid, new_status)
    else:
        logger.warning("No outgoing message found for SID=%s", message_sid)

    # Also update NotificationLog if it exists
    from .models import NotificationLog

    notif_status_map = {
        WhatsAppMessage.Status.DELIVERED: NotificationLog.Status.DELIVERED,
        WhatsAppMessage.Status.READ: NotificationLog.Status.DELIVERED,
        WhatsAppMessage.Status.FAILED: NotificationLog.Status.FAILED,
    }
    notif_status = notif_status_map.get(new_status)
    if notif_status:
        notif_updated = NotificationLog.objects.filter(twilio_sid=message_sid).update(
            status=notif_status,
            error_detail=f"{error_code}: {error_message}" if error_code else "",
        )
        if notif_updated:
            logger.info("Updated %d notification(s) SID=%s → %s", notif_updated, message_sid, notif_status)

    return HttpResponse(status=200)
