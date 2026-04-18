"""
Tests for the WhatsApp messaging module.
"""

from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.utils import timezone

from accounts.models import User
from transport.customers.models import Customer
from transport.core.models import CommodityType
from transport.drivers.models import Driver
from transport.routes.models import Route
from transport.trips.models import Trip
from transport.vehicles.models import Vehicle

from transport.messaging.commands import parse_and_execute, _sessions
from transport.messaging.models import FuelRequest, WhatsAppMessage, NotificationLog


class CommandParserTestCase(TestCase):
    """Test the WhatsApp command parser without actually sending messages."""

    @classmethod
    def setUpTestData(cls):
        cls.customer = Customer.objects.create(
            company_name="Test Corp",
            phone="+250788000001",
        )
        cls.route = Route.objects.create(
            origin="Kigali",
            destination="Rubavu",
            distance_km=160,
        )
        cls.commodity = CommodityType.objects.create(
            code=CommodityType.Code.GOODS,
            name="Goods",
        )
        tomorrow = timezone.now().date() + timezone.timedelta(days=365)
        cls.vehicle = Vehicle.objects.create(
            plate_number="RAB123A",
            capacity=20000,
            insurance_expiry=tomorrow,
            inspection_expiry=tomorrow,
        )
        cls.driver = Driver.objects.create(
            name="Jean Claude",
            phone="+250788100200",
            license_number="DL-001",
            license_expiry=tomorrow,
        )
        cls.trip = Trip.objects.create(
            customer=cls.customer,
            route=cls.route,
            commodity_type=cls.commodity,
            vehicle=cls.vehicle,
            driver=cls.driver,
            status=Trip.TripStatus.ASSIGNED,
            revenue=Decimal("500000"),
        )
        # Manager user
        cls.manager = User.objects.create_user(
            email="manager@test.com",
            password="testpass123",
            full_name="Manager One",
            role=User.Role.MANAGER,
            phone="+250788999888",
        )

    def setUp(self):
        # Clear sessions between tests
        _sessions.clear()

    # ---- HELP ----

    def test_help_command(self):
        reply = parse_and_execute("+250788100200", "HELP")
        self.assertIn("ZALA Terminal WhatsApp Menu", reply)
        self.assertIn("Accept", reply)

    def test_help_case_insensitive(self):
        reply = parse_and_execute("+250788100200", "help")
        self.assertIn("ZALA Terminal WhatsApp Menu", reply)

    def test_help_hi(self):
        reply = parse_and_execute("+250788100200", "Hi")
        self.assertIn("ZALA Terminal WhatsApp Menu", reply)

    # ---- Numbered shortcuts ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_accept_shortcut_1(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", "1")
        self.assertIn("accepted", reply.lower())

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_decline_shortcut_2(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", "2")
        self.assertIn("declined", reply.lower())

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_accept_yes(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", "YES")
        self.assertIn("accepted", reply.lower())

    # ---- ACCEPT ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_accept_command(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", f"ACCEPT {self.trip.order_number}")
        self.assertIn("accepted", reply.lower())
        self.assertIn(self.trip.order_number, reply)

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_accept_unknown_phone(self, mock_send):
        reply = parse_and_execute("+250788000000", f"ACCEPT {self.trip.order_number}")
        self.assertIn("not linked", reply.lower())

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_accept_wrong_driver(self, mock_send):
        other_driver = Driver.objects.create(
            name="Other",
            phone="+250788111222",
            license_number="DL-002",
            license_expiry=timezone.now().date() + timezone.timedelta(days=365),
        )
        reply = parse_and_execute("+250788111222", f"ACCEPT {self.trip.order_number}")
        self.assertIn("not assigned to you", reply.lower())

    # ---- DECLINE ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_decline_command(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", f"DECLINE {self.trip.order_number}")
        self.assertIn("declined", reply.lower())

    # ---- START + KM ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_start_then_km(self, mock_send):
        mock_send.return_value = None
        phone = "+250788100200"

        reply = parse_and_execute(phone, f"START {self.trip.order_number}")
        self.assertIn("KM", reply)

        reply = parse_and_execute(phone, "KM 125430")
        self.assertIn("IN TRANSIT", reply)

        self.trip.refresh_from_db()
        self.assertEqual(self.trip.km_start, Decimal("125430"))
        self.assertEqual(self.trip.status, Trip.TripStatus.IN_TRANSIT)

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_start_wrong_status(self, mock_send):
        self.trip.status = Trip.TripStatus.DRAFT
        self.trip.save(update_fields=["status", "updated_at"])

        reply = parse_and_execute("+250788100200", f"START {self.trip.order_number}")
        self.assertIn("cannot be started", reply.lower())

    # ---- DELIVERED ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_delivered_command(self, mock_send):
        mock_send.return_value = None
        self.trip.status = Trip.TripStatus.IN_TRANSIT
        self.trip.km_start = Decimal("125430")
        self.trip.save(update_fields=["status", "km_start", "updated_at"])
        phone = "+250788100200"

        # Step 1: driver sends DELIVERED ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ system asks for odometer end
        reply = parse_and_execute(phone, f"DELIVERED {self.trip.order_number}")
        self.assertIn("odometer", reply.lower())
        self.assertIn("125430", reply)  # shows km_start

        # Step 2: driver sends KM end reading
        reply = parse_and_execute(phone, "125890")
        self.assertIn("DELIVERED", reply)
        self.assertIn("460", reply)  # distance = 125890 - 125430

        self.trip.refresh_from_db()
        self.assertEqual(self.trip.status, Trip.TripStatus.DELIVERED)
        self.assertEqual(self.trip.km_end, Decimal("125890"))
        self.assertEqual(self.trip.distance, Decimal("460"))

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_delivered_invalid_km_end(self, mock_send):
        """KM end less than KM start should be rejected."""
        mock_send.return_value = None
        self.trip.status = Trip.TripStatus.IN_TRANSIT
        self.trip.km_start = Decimal("125430")
        self.trip.save(update_fields=["status", "km_start", "updated_at"])
        phone = "+250788100200"

        parse_and_execute(phone, "4")  # trigger delivery
        reply = parse_and_execute(phone, "100")  # less than km_start
        self.assertIn("cannot be less", reply.lower())

    # ---- FUEL REQUEST ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_fuel_request(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute(
            "+250788100200",
            f"FUEL REQUEST {self.trip.order_number} 100",
        )
        self.assertIn("submitted", reply.lower())
        self.assertEqual(FuelRequest.objects.count(), 1)
        fr = FuelRequest.objects.first()
        self.assertEqual(fr.liters_requested, Decimal("100"))
        self.assertEqual(fr.status, FuelRequest.Status.PENDING)

    # ---- APPROVE ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_approve_fuel_request(self, mock_send):
        mock_send.return_value = None
        fr = FuelRequest.objects.create(
            driver=self.driver,
            trip=self.trip,
            liters_requested=Decimal("80"),
        )
        reply = parse_and_execute("+250788999888", f"APPROVE {fr.pk}")
        self.assertIn("approved", reply.lower())

        fr.refresh_from_db()
        self.assertEqual(fr.status, FuelRequest.Status.APPROVED)

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_approve_non_manager(self, mock_send):
        fr = FuelRequest.objects.create(
            driver=self.driver,
            trip=self.trip,
            liters_requested=Decimal("50"),
        )
        reply = parse_and_execute("+250788100200", f"APPROVE {fr.pk}")
        self.assertIn("not authorized", reply.lower())

    # ---- REJECT ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_reject_fuel_request(self, mock_send):
        mock_send.return_value = None
        fr = FuelRequest.objects.create(
            driver=self.driver,
            trip=self.trip,
            liters_requested=Decimal("50"),
        )
        reply = parse_and_execute("+250788999888", f"REJECT {fr.pk}")
        self.assertIn("rejected", reply.lower())

        fr.refresh_from_db()
        self.assertEqual(fr.status, FuelRequest.Status.REJECTED)

    # ---- STATUS ----

    def test_status_command(self):
        reply = parse_and_execute("+250788100200", f"STATUS {self.trip.order_number}")
        self.assertIn(self.trip.order_number, reply)
        self.assertIn("Test Corp", reply)
        self.assertIn("Kigali", reply)

    # ---- Unknown ----

    def test_unknown_command(self):
        reply = parse_and_execute("+250788100200", "FOOBAR")
        self.assertIn("HELP", reply)

    # ---- Bare number when awaiting KM ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_bare_number_as_km(self, mock_send):
        mock_send.return_value = None
        phone = "+250788100200"
        parse_and_execute(phone, f"START {self.trip.order_number}")

        reply = parse_and_execute(phone, "125430")
        self.assertIn("IN TRANSIT", reply)

    # ---- Shortcut 3 = START (auto finds active trip) ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_start_shortcut_3(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", "3")
        self.assertIn("Starting trip", reply)

    # ---- FUEL shortcut ----

    @patch("transport.messaging.commands.send_whatsapp_message")
    def test_fuel_shortcut(self, mock_send):
        mock_send.return_value = None
        reply = parse_and_execute("+250788100200", "FUEL 50")
        self.assertIn("submitted", reply.lower())
        self.assertEqual(FuelRequest.objects.count(), 1)

    # ---- STATUS without order number ----

    def test_status_shortcut(self):
        reply = parse_and_execute("+250788100200", "STATUS")
        self.assertIn(self.trip.order_number, reply)


class WebhookViewTestCase(TestCase):
    """Test the Twilio webhook endpoint."""

    def setUp(self):
        self.factory = RequestFactory()

    @patch("transport.messaging.views._validate_twilio_request", return_value=True)
    @patch("transport.messaging.commands.send_whatsapp_message", return_value=None)
    def test_webhook_receives_message(self, mock_send, mock_validate):
        from transport.messaging.views import whatsapp_webhook

        response = self.client.post(
            "/api/whatsapp/webhook/",
            data={
                "From": "whatsapp:+250788100200",
                "Body": "HELP",
                "MessageSid": "SM_test123",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WhatsAppMessage.objects.filter(direction="incoming").count(), 1)


class ModelTestCase(TestCase):
    """Basic model tests."""

    def test_whatsapp_message_str(self):
        msg = WhatsAppMessage.objects.create(
            phone_number="+250788100200",
            message="HELP",
            direction=WhatsAppMessage.Direction.INCOMING,
        )
        self.assertIn("+250788100200", str(msg))

    def test_notification_log_str(self):
        log = NotificationLog.objects.create(
            phone_number="+250788100200",
            message="Test",
        )
        self.assertIn("+250788100200", str(log))
