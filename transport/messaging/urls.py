from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("webhook/", views.whatsapp_webhook, name="whatsapp-webhook"),
    path("status/", views.whatsapp_status_callback, name="whatsapp-status"),
]
