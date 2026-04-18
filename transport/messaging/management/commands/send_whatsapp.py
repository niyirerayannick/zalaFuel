"""
Management command: send_whatsapp

Quick way to send a test WhatsApp message from the command line.

Usage:
    python manage.py send_whatsapp +250788100200 "Hello from ZALA/ECO ENERGY"
"""

from django.core.management.base import BaseCommand

from transport.messaging.twilio_client import send_whatsapp_message


class Command(BaseCommand):
    help = "Send a WhatsApp message through Twilio."

    def add_arguments(self, parser):
        parser.add_argument("phone", type=str, help="Recipient phone number")
        parser.add_argument("message", type=str, help="Message body")

    def handle(self, *args, **options):
        phone = options["phone"]
        message = options["message"]

        self.stdout.write(f"Sending WhatsApp to {phone} ...")
        sid = send_whatsapp_message(phone, message)

        if sid:
            self.stdout.write(self.style.SUCCESS(f"Sent! SID: {sid}"))
        else:
            self.stdout.write(self.style.WARNING(
                "Message logged but NOT sent (Twilio credentials not configured or dry-run mode)."
            ))
