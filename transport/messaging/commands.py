"""
WhatsApp command parser.

Drivers and managers text commands to the WhatsApp number.  This module
parses the incoming text and dispatches to the correct handler, returning
a reply string.

Supported commands (simplified for drivers)
--------------------------------------------
1 or YES or ACCEPT   ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Accept the current assigned trip
2 or NO or DECLINE   ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Decline the current assigned trip
3 or START            ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Start the trip (then send KM reading)
<number>              ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ KM reading (when awaiting)
4 or DONE/DELIVERED   ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Mark trip delivered
FUEL <liters>         ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Request fuel for current trip
APPROVE <id>          ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Approve fuel request (managers)
REJECT <id>           ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Reject fuel request (managers)
STATUS                ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Check current trip status
HELP or HI or MENU   ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ Show available commands
"""

import logging
import re
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from transport.drivers.models import Driver
from transport.trips.models import Trip

from .models import FuelRequest, WhatsAppMessage
from .twilio_client import send_whatsapp_message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session store ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ maps phone ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ context (current trip, pending action, etc.)
# In production this should be Redis / DB backed; dict is fine for a start.
# ---------------------------------------------------------------------------

_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_driver_by_phone(phone: str) -> Driver | None:
    """Look up a driver by their phone number (flexible matching)."""
    clean = phone.replace("whatsapp:", "").strip()
    # Try exact match first
    driver = Driver.objects.filter(phone=clean).first()
    if driver:
        return driver
    # Try with country code variants
    if clean.startswith("+250"):
        local = "0" + clean[4:]
        driver = Driver.objects.filter(phone=local).first()
    elif clean.startswith("0"):
        intl = "+250" + clean[1:]
        driver = Driver.objects.filter(phone=intl).first()
    return driver


def _find_trip(order_number: str) -> Trip | None:
    """Find trip by order_number (case-insensitive)."""
    return Trip.objects.filter(order_number__iexact=order_number.strip()).first()


def _get_active_trip(driver: Driver) -> Trip | None:
    """Get the driver's current active trip (ASSIGNED or IN_TRANSIT)."""
    return Trip.objects.filter(
        driver=driver,
        status__in=[Trip.TripStatus.ASSIGNED, Trip.TripStatus.IN_TRANSIT],
    ).order_by("-created_at").first()


def _notify_managers(message: str):
    """Send a WhatsApp notification to all manager-role users that have a phone."""
    from accounts.models import User

    managers = User.objects.filter(
        role__in=[User.Role.MANAGER, User.Role.ADMIN, User.Role.SUPERADMIN],
        is_active=True,
    ).exclude(phone="")
    for mgr in managers:
        send_whatsapp_message(mgr.phone, message)


# ---------------------------------------------------------------------------
# Command handlers  (each returns a reply string)
# ---------------------------------------------------------------------------

def _handle_accept(phone: str, order_number: str = None) -> str:
    driver = _find_driver_by_phone(phone)
    if not driver:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account. Contact admin."

    # If no order number given, find the driver's current ASSIGNED trip
    if order_number:
        trip = _find_trip(order_number)
    else:
        trip = Trip.objects.filter(
            driver=driver, status=Trip.TripStatus.ASSIGNED
        ).order_by("-created_at").first()

    if not trip:
        return "No assigned trip found."
    if trip.driver_id != driver.pk:
        return "This trip is not assigned to you."
    if trip.status != Trip.TripStatus.ASSIGNED:
        return f"Trip {trip.order_number} cannot be accepted (status: {trip.get_status_display()})."

    # Record acceptance, notify managers
    _notify_managers(
        f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Driver {driver.name} ACCEPTED trip {trip.order_number}."
    )

    # Store trip in session for easy follow-up commands
    _sessions[phone] = {"trip_id": trip.pk, "action": "accepted"}

    return (
        f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ You accepted trip *{trip.order_number}*\n\n"
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â {trip.route.origin} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.route.destination}\n"
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â‚¬Âº {trip.vehicle.plate_number}\n"
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â¦ {trip.customer.company_name}\n\n"
        f"When ready to depart, reply:\n"
        f"*3* or *START*"
    )


def _handle_decline(phone: str, order_number: str = None) -> str:
    driver = _find_driver_by_phone(phone)
    if not driver:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account. Contact admin."

    if order_number:
        trip = _find_trip(order_number)
    else:
        trip = Trip.objects.filter(
            driver=driver, status=Trip.TripStatus.ASSIGNED
        ).order_by("-created_at").first()

    if not trip:
        return "No assigned trip found."
    if trip.driver_id != driver.pk:
        return "This trip is not assigned to you."
    if trip.status != Trip.TripStatus.ASSIGNED:
        return f"Trip {trip.order_number} cannot be declined (status: {trip.get_status_display()})."

    _notify_managers(
        f"ÃƒÂ¢Ã…Â¡Ã‚Â ÃƒÂ¯Ã‚Â¸Ã‚Â Driver {driver.name} DECLINED trip {trip.order_number}. "
        "Please reassign."
    )
    _sessions.pop(phone, None)
    return f"ÃƒÂ¢Ã‚ÂÃ…â€™ You declined trip *{trip.order_number}*. A manager has been notified."


def _handle_start(phone: str, order_number: str = None) -> str:
    driver = _find_driver_by_phone(phone)
    if not driver:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account. Contact admin."

    if order_number:
        trip = _find_trip(order_number)
    else:
        trip = _get_active_trip(driver)

    if not trip:
        return "No active trip found."
    if trip.driver_id != driver.pk:
        return "This trip is not assigned to you."
    if trip.status != Trip.TripStatus.ASSIGNED:
        return f"Trip {trip.order_number} cannot be started (status: {trip.get_status_display()})."

    # Store session ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ waiting for KM reading
    _sessions[phone] = {"action": "awaiting_km", "trip_id": trip.pk}
    return (
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ Starting trip *{trip.order_number}*\n\n"
        f"Please send your current KM reading.\n"
        f"Just type the number, e.g.: *125430*"
    )


def _handle_km(phone: str, reading_str: str) -> str:
    session = _sessions.get(phone)
    if not session or session.get("action") != "awaiting_km":
        return "No pending trip start. Reply *3* or *START* first."

    try:
        km_reading = Decimal(reading_str.replace(",", ""))
    except (InvalidOperation, ValueError):
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Invalid KM reading. Please send a number, e.g. *125430*"

    trip = Trip.objects.filter(pk=session["trip_id"]).first()
    if not trip:
        _sessions.pop(phone, None)
        return "Trip no longer exists."

    with transaction.atomic():
        trip.km_start = km_reading
        trip.status = Trip.TripStatus.IN_TRANSIT
        trip.save(update_fields=[
            "km_start", "status", "updated_at",
            "distance", "total_cost", "profit", "cost_per_km", "revenue_per_km",
        ])

    _sessions[phone] = {"trip_id": trip.pk, "action": "in_transit"}

    # Notify customer
    _send_customer_trip_started(trip)

    return (
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã…Â¡ Trip *{trip.order_number}* is now *IN TRANSIT*\n"
        f"KM start: {km_reading}\n\n"
        f"When delivered, reply:\n"
        f"*4* or *DONE*"
    )


def _handle_delivered(phone: str, order_number: str = None) -> str:
    driver = _find_driver_by_phone(phone)
    if not driver:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account. Contact admin."

    if order_number:
        trip = _find_trip(order_number)
    else:
        trip = Trip.objects.filter(
            driver=driver, status=Trip.TripStatus.IN_TRANSIT
        ).order_by("-created_at").first()

    if not trip:
        return "No in-transit trip found."
    if trip.driver_id != driver.pk:
        return "This trip is not assigned to you."
    if trip.status != Trip.TripStatus.IN_TRANSIT:
        return f"Trip {trip.order_number} cannot be marked delivered (status: {trip.get_status_display()})."

    # Ask for odometer end reading before completing delivery
    _sessions[phone] = {"action": "awaiting_km_end", "trip_id": trip.pk}
    return (
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Confirming delivery for *{trip.order_number}*\n\n"
        f"KM start was: *{trip.km_start}*\n\n"
        f"Please send your current odometer reading.\n"
        f"Just type the number, e.g.: *125890*"
    )


def _handle_km_end(phone: str, reading_str: str) -> str:
    """Process the odometer end reading and complete delivery."""
    session = _sessions.get(phone)
    if not session or session.get("action") != "awaiting_km_end":
        return "No pending delivery. Reply *4* or *DONE* first."

    try:
        km_reading = Decimal(reading_str.replace(",", ""))
    except (InvalidOperation, ValueError):
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Invalid KM reading. Please send a number, e.g. *125890*"

    trip = Trip.objects.filter(pk=session["trip_id"]).first()
    if not trip:
        _sessions.pop(phone, None)
        return "Trip no longer exists."

    # Validate km_end >= km_start
    if km_reading < trip.km_start:
        return (
            f"ÃƒÂ¢Ã‚ÂÃ…â€™ Odometer end (*{km_reading}*) cannot be less than "
            f"odometer start (*{trip.km_start}*).\n"
            f"Please send the correct reading."
        )

    driver = trip.driver

    with transaction.atomic():
        trip.km_end = km_reading
        trip.status = Trip.TripStatus.DELIVERED
        # Recalculate distance
        trip.distance = trip.km_end - trip.km_start
        trip.save(update_fields=[
            "km_end", "status", "updated_at",
            "distance", "total_cost", "profit", "cost_per_km", "revenue_per_km",
        ])

        # Also update linked order if exists
        if hasattr(trip, "order") and trip.order:
            order = trip.order
            order.status = "completed"
            order.save(update_fields=["status", "updated_at"])

    # Notify customer
    _send_customer_delivery(trip)

    _notify_managers(
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â¦ Trip {trip.order_number} marked DELIVERED by {driver.name}.\n"
        f"Distance: {trip.distance} km (KM {trip.km_start} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.km_end})"
    )
    _sessions.pop(phone, None)
    return (
        f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Trip *{trip.order_number}* marked as *DELIVERED*\n\n"
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂºÃ‚Â£ÃƒÂ¯Ã‚Â¸Ã‚Â KM: {trip.km_start} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.km_end}\n"
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã‚Â Distance: *{trip.distance} km*\n\n"
        f"Thank you, {driver.name}! ÃƒÂ°Ã…Â¸Ã…Â½Ã¢â‚¬Â°"
    )


def _handle_fuel_request(phone: str, order_number: str = None, liters_str: str = "") -> str:
    driver = _find_driver_by_phone(phone)
    if not driver:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account. Contact admin."

    # If order_number looks like a number (liters), treat it as liters with auto trip
    if order_number and not liters_str:
        try:
            Decimal(order_number.replace(",", ""))
            # It's actually a liter value, use active trip
            liters_str = order_number
            order_number = None
        except (InvalidOperation, ValueError):
            pass

    if order_number:
        trip = _find_trip(order_number)
    else:
        trip = _get_active_trip(driver)

    if not trip:
        return "No active trip found for fuel request."
    if trip.driver_id != driver.pk:
        return "This trip is not assigned to you."

    if not liters_str:
        return "Please specify liters. Example: *FUEL 100*"

    try:
        liters = Decimal(liters_str.replace(",", ""))
    except (InvalidOperation, ValueError):
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Invalid liter amount. Example: *FUEL 100*"

    fuel_req = FuelRequest.objects.create(
        driver=driver,
        trip=trip,
        liters_requested=liters,
    )

    _notify_managers(
        f"ÃƒÂ¢Ã¢â‚¬ÂºÃ‚Â½ Fuel Request #{fuel_req.pk}\n"
        f"Driver: {driver.name}\n"
        f"Trip: {trip.order_number}\n"
        f"Liters: {liters}\n\n"
        f"Reply:\n"
        f"*APPROVE {fuel_req.pk}*\n"
        f"*REJECT {fuel_req.pk}*"
    )
    return (
        f"ÃƒÂ¢Ã¢â‚¬ÂºÃ‚Â½ Fuel request submitted: *{liters}L*\n"
        f"Trip: {trip.order_number}\n"
        f"Waiting for manager approval."
    )


def _handle_approve(phone: str, request_id_str: str) -> str:
    """Manager approves a fuel request."""
    from accounts.models import User

    clean_phone = phone.replace("whatsapp:", "").strip()
    user = User.objects.filter(
        phone__in=[
            clean_phone,
            f"+250{clean_phone[1:]}" if clean_phone.startswith("0") else clean_phone,
            f"0{clean_phone[4:]}" if clean_phone.startswith("+250") else clean_phone,
        ],
        role__in=[User.Role.MANAGER, User.Role.ADMIN, User.Role.SUPERADMIN],
        is_active=True,
    ).first()
    if not user:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ You are not authorized to approve fuel requests."

    try:
        req_id = int(request_id_str)
    except ValueError:
        return "Invalid request ID."

    fuel_req = FuelRequest.objects.filter(pk=req_id, status=FuelRequest.Status.PENDING).first()
    if not fuel_req:
        return f"Fuel request #{request_id_str} not found or already processed."

    fuel_req.status = FuelRequest.Status.APPROVED
    fuel_req.approved_by = user
    fuel_req.save(update_fields=["status", "approved_by", "updated_at"])

    # Notify driver
    send_whatsapp_message(
        fuel_req.driver.phone,
        f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Your fuel request #{fuel_req.pk} has been *APPROVED*.\n"
        f"Trip: {fuel_req.trip.order_number}\n"
        f"Liters: {fuel_req.liters_requested}L\n"
        f"Approved by: {user.full_name}",
    )
    return f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Fuel request #{fuel_req.pk} approved."


def _handle_reject(phone: str, request_id_str: str) -> str:
    """Manager rejects a fuel request."""
    from accounts.models import User

    clean_phone = phone.replace("whatsapp:", "").strip()
    user = User.objects.filter(
        phone__in=[
            clean_phone,
            f"+250{clean_phone[1:]}" if clean_phone.startswith("0") else clean_phone,
            f"0{clean_phone[4:]}" if clean_phone.startswith("+250") else clean_phone,
        ],
        role__in=[User.Role.MANAGER, User.Role.ADMIN, User.Role.SUPERADMIN],
        is_active=True,
    ).first()
    if not user:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ You are not authorized to reject fuel requests."

    try:
        req_id = int(request_id_str)
    except ValueError:
        return "Invalid request ID."

    fuel_req = FuelRequest.objects.filter(pk=req_id, status=FuelRequest.Status.PENDING).first()
    if not fuel_req:
        return f"Fuel request #{request_id_str} not found or already processed."

    fuel_req.status = FuelRequest.Status.REJECTED
    fuel_req.save(update_fields=["status", "updated_at"])

    send_whatsapp_message(
        fuel_req.driver.phone,
        f"ÃƒÂ¢Ã‚ÂÃ…â€™ Your fuel request #{fuel_req.pk} has been *REJECTED*.\n"
        f"Trip: {fuel_req.trip.order_number}\n"
        f"Contact your manager for details.",
    )
    return f"ÃƒÂ¢Ã‚ÂÃ…â€™ Fuel request #{fuel_req.pk} rejected."


def _handle_status(phone: str, order_number: str = None) -> str:
    driver = _find_driver_by_phone(phone)

    if order_number:
        trip = _find_trip(order_number)
    elif driver:
        trip = _get_active_trip(driver)
    else:
        return "ÃƒÂ¢Ã‚ÂÃ…â€™ Your phone number is not linked to a driver account."

    if not trip:
        return "No active trip found."

    pending_fuel = FuelRequest.objects.filter(
        trip=trip, status=FuelRequest.Status.PENDING
    ).count()

    return (
        f"ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬Â¹ *Trip {trip.order_number}*\n\n"
        f"Status: *{trip.get_status_display()}*\n"
        f"Customer: {trip.customer.company_name}\n"
        f"Route: {trip.route.origin} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.route.destination}\n"
        f"Vehicle: {trip.vehicle.plate_number}\n"
        f"Driver: {trip.driver.name}\n"
        f"KM: {trip.km_start} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.km_end or 'ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â'}\n"
        f"Pending fuel requests: {pending_fuel}"
    )


def _handle_help(phone: str) -> str:
    driver = _find_driver_by_phone(phone)
    trip = _get_active_trip(driver) if driver else None

    menu = "ÃƒÂ°Ã…Â¸Ã¢â‚¬Å“Ã¢â‚¬â€œ *ZALA Terminal WhatsApp Menu*\n\n"

    if trip and trip.status == Trip.TripStatus.ASSIGNED:
        menu += (
            f"You have trip *{trip.order_number}* waiting.\n\n"
            f"*1* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Accept trip\n"
            f"*2* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ÃƒÂ¢Ã‚ÂÃ…â€™ Decline trip\n"
            f"*3* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ÃƒÂ°Ã…Â¸Ã…Â¡Ã¢â€šÂ¬ Start trip\n"
        )
    elif trip and trip.status == Trip.TripStatus.IN_TRANSIT:
        menu += (
            f"Trip *{trip.order_number}* is in transit.\n\n"
            f"*4* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ Mark delivered\n"
            f"*FUEL <liters>* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â ÃƒÂ¢Ã¢â‚¬ÂºÃ‚Â½ Request fuel\n"
        )
    else:
        menu += "No active trip right now.\n\n"

    menu += (
        "\n*All Commands:*\n"
        "*1* or *YES* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Accept trip\n"
        "*2* or *NO* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Decline trip\n"
        "*3* or *START* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Start trip\n"
        "*4* or *DONE* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Mark delivered\n"
        "*FUEL <liters>* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Request fuel\n"
        "*STATUS* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Check trip status\n"
        "*HELP* ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Show this menu"
    )
    return menu


# ---------------------------------------------------------------------------
# Customer notification helpers
# ---------------------------------------------------------------------------

def _send_customer_trip_started(trip: Trip):
    """Notify customer that their shipment has started."""
    phone = trip.customer.phone
    if not phone:
        return
    send_whatsapp_message(
        phone,
        f"ÃƒÂ°Ã…Â¸Ã…Â¡Ã…Â¡ *ZALA Terminal*\n\n"
        f"Your shipment *{trip.order_number}* has started.\n"
        f"Route: {trip.route.origin} ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ {trip.route.destination}\n"
        f"Driver: {trip.driver.name}\n\n"
        f"We'll notify you upon delivery.",
    )


def _send_customer_delivery(trip: Trip):
    """Notify customer that their shipment has been delivered."""
    phone = trip.customer.phone
    if not phone:
        return
    send_whatsapp_message(
        phone,
        f"ÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ *ZALA Terminal*\n\n"
        f"Your shipment *{trip.order_number}* has been delivered.\n"
        f"Thank you for choosing ZALA Terminal! ÃƒÂ°Ã…Â¸Ã…Â½Ã¢â‚¬Â°",
    )


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

# Regex patterns for command matching ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â numbered shortcuts come first
_PATTERNS = [
    # Numbered shortcuts (driver-friendly)
    (re.compile(r"^1$"), "accept"),
    (re.compile(r"^2$"), "decline"),
    (re.compile(r"^3$"), "start"),
    (re.compile(r"^4$"), "delivered"),

    # Word shortcuts
    (re.compile(r"^(?:YES|Y|OK|ACCEPT)$", re.IGNORECASE), "accept"),
    (re.compile(r"^(?:NO|N|DECLINE)$", re.IGNORECASE), "decline"),
    (re.compile(r"^(?:START|GO|BEGIN)$", re.IGNORECASE), "start"),
    (re.compile(r"^(?:DONE|DELIVERED|COMPLETE|FINISH)$", re.IGNORECASE), "delivered"),

    # With order number (still supported)
    (re.compile(r"^ACCEPT\s+(.+)$", re.IGNORECASE), "accept_order"),
    (re.compile(r"^DECLINE\s+(.+)$", re.IGNORECASE), "decline_order"),
    (re.compile(r"^START\s+(.+)$", re.IGNORECASE), "start_order"),
    (re.compile(r"^DELIVERED\s+(.+)$", re.IGNORECASE), "delivered_order"),

    # KM reading
    (re.compile(r"^KM\s+([\d,\.]+)$", re.IGNORECASE), "km"),

    # Fuel request ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â "FUEL 100" or "FUEL REQUEST <order> <liters>"
    (re.compile(r"^FUEL\s+([\d,\.]+)$", re.IGNORECASE), "fuel_simple"),
    (re.compile(r"^FUEL\s+REQUEST\s+(\S+)\s+([\d,\.]+)$", re.IGNORECASE), "fuel_request"),

    # Manager commands
    (re.compile(r"^APPROVE\s+(\d+)$", re.IGNORECASE), "approve"),
    (re.compile(r"^REJECT\s+(\d+)$", re.IGNORECASE), "reject"),

    # Info commands
    (re.compile(r"^STATUS(?:\s+(.+))?$", re.IGNORECASE), "status"),
    (re.compile(r"^(?:HELP|HI|HELLO|MENU|H|\?)$", re.IGNORECASE), "help"),
]


def parse_and_execute(phone: str, body: str) -> str:
    """
    Parse an incoming WhatsApp message body and execute the command.

    Returns the reply text to send back to the user.
    """
    body = body.strip()

    for pattern, cmd_name in _PATTERNS:
        match = pattern.match(body)
        if match:
            groups = match.groups()

            # Numbered / word shortcuts (no order_number needed)
            if cmd_name == "accept":
                return _handle_accept(phone)
            if cmd_name == "decline":
                return _handle_decline(phone)
            if cmd_name == "start":
                return _handle_start(phone)
            if cmd_name == "delivered":
                return _handle_delivered(phone)

            # With explicit order number
            if cmd_name == "accept_order":
                return _handle_accept(phone, groups[0])
            if cmd_name == "decline_order":
                return _handle_decline(phone, groups[0])
            if cmd_name == "start_order":
                return _handle_start(phone, groups[0])
            if cmd_name == "delivered_order":
                return _handle_delivered(phone, groups[0])

            # KM reading
            if cmd_name == "km":
                return _handle_km(phone, groups[0])

            # Fuel
            if cmd_name == "fuel_simple":
                return _handle_fuel_request(phone, None, groups[0])
            if cmd_name == "fuel_request":
                return _handle_fuel_request(phone, groups[0], groups[1])

            # Manager
            if cmd_name == "approve":
                return _handle_approve(phone, groups[0])
            if cmd_name == "reject":
                return _handle_reject(phone, groups[0])

            # Info
            if cmd_name == "status":
                return _handle_status(phone, groups[0] if groups else None)
            if cmd_name == "help":
                return _handle_help(phone)

    # If there's an active session (e.g. awaiting KM), try handling as bare number
    session = _sessions.get(phone)
    if session:
        action = session.get("action")
        if action == "awaiting_km":
            try:
                Decimal(body.replace(",", ""))
                return _handle_km(phone, body)
            except (InvalidOperation, ValueError):
                pass
        elif action == "awaiting_km_end":
            try:
                Decimal(body.replace(",", ""))
                return _handle_km_end(phone, body)
            except (InvalidOperation, ValueError):
                pass

    return (
        "ÃƒÂ°Ã…Â¸Ã‚Â¤Ã¢â‚¬Â Sorry, I didn't understand that.\n\n"
        "Reply *HELP* or *MENU* to see available commands."
    )
