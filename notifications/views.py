from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class NotificationListView(LoginRequiredMixin, TemplateView):
    template_name = "notifications/list.html"
    extra_context = {"page_title": "Notifications", "active_menu": "notifications"}
