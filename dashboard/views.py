from django.views.generic import TemplateView

from accounts.models import SystemSettings
from accounts.mixins import DashboardRoleMixin
from accounts.currency import CURRENCY_SYMBOLS

from .services import dashboard_snapshot


class DashboardHomeView(DashboardRoleMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        settings = SystemSettings.get_settings()
        currency_code = getattr(settings, "currency", "USD") or "USD"
        currency_symbol = (
            getattr(settings, "currency_symbol", "")
            or CURRENCY_SYMBOLS.get(currency_code, currency_code)
        )
        context.update(
            {
                "page_title": "Dashboard",
                "active_menu": "dashboard",
                "dashboard_currency_code": currency_code,
                "dashboard_currency_symbol": currency_symbol,
                **dashboard_snapshot(),
            }
        )
        return context
