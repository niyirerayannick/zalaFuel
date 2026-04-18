"""
Signals that integrate WhatsApp messaging with the trip lifecycle.

We listen for Trip status changes and fire WhatsApp notifications
accordingly.  All notifications are best-effort – failures are logged
but never block the web workflow.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from transport.trips.models import Trip

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Trip)
def trip_whatsapp_notifications(sender, instance, created, **kwargs):
    """
    React to Trip saves and send WhatsApp notifications where appropriate.

    - ASSIGNED → notify driver of new trip assignment
    - IN_TRANSIT → notify customer that shipment has started
    - DELIVERED → notify customer that shipment has arrived
    """
    # Import lazily to avoid circular imports at startup
    from .services import (
        notify_customer_delivered,
        notify_customer_trip_started,
        notify_driver_trip_assigned,
    )

    logger.info(
        "Trip signal fired: %s status=%s created=%s",
        instance.order_number, instance.status, created,
    )

    try:
        if instance.status == Trip.TripStatus.ASSIGNED:
            logger.info("Sending ASSIGNED notification for %s", instance.order_number)
            notify_driver_trip_assigned(instance)

        elif instance.status == Trip.TripStatus.IN_TRANSIT:
            logger.info("Sending IN_TRANSIT notification for %s", instance.order_number)
            notify_customer_trip_started(instance)

        elif instance.status == Trip.TripStatus.DELIVERED:
            logger.info("Sending DELIVERED notification for %s", instance.order_number)
            notify_customer_delivered(instance)

        else:
            logger.debug(
                "Trip %s status=%s – no WhatsApp notification for this status.",
                instance.order_number, instance.status,
            )

    except Exception:
        # Never let messaging failures break the web workflow
        logger.exception(
            "WhatsApp notification failed for trip %s (status=%s)",
            instance.order_number,
            instance.status,
        )
