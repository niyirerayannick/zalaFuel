from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import User
from .rbac import SystemGroup, user_has_role


def build_public_url(path):
    base_url = getattr(settings, "ATMS_PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def approval_recipients(*roles):
    recipients = []
    for user in User.objects.filter(is_active=True).order_by("email"):
        if not user.email:
            continue
        if user_has_role(user, *roles):
            recipients.append(user.email)
    return list(dict.fromkeys(recipients))


def send_atms_email(
    *,
    subject,
    to,
    greeting,
    headline,
    intro,
    details=None,
    note=None,
    cta_label=None,
    cta_url=None,
    closing="ZALA Terminal Notification Center",
    attachments=None,
):
    details = details or []
    attachments = attachments or []

    context = {
        "subject": subject,
        "greeting": greeting,
        "headline": headline,
        "intro": intro,
        "details": details,
        "note": note,
        "cta_label": cta_label,
        "cta_url": cta_url,
        "closing": closing,
        "from_name": getattr(settings, "EMAIL_FROM_NAME", "ZALA Terminal Notification Center"),
        "company_name": "ZALA Terminal",
    }

    text_body = render_to_string("emails/base.txt", context)
    html_body = render_to_string("emails/base.html", context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    email.attach_alternative(html_body, "text/html")
    for attachment in attachments:
        email.attach(*attachment)
    email.send(fail_silently=False)
    return email
