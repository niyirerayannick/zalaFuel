from django.views.generic import TemplateView

from accounts.mixins import ReportsRoleMixin
from tanks.models import Tank

from .models import Alert


class MonitoringDashboardView(ReportsRoleMixin, TemplateView):
    template_name = "monitoring/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        alerts = Alert.objects.select_related("terminal", "tank", "product", "omc").order_by("-triggered_at")
        context.update(
            {
                "page_title": "Monitoring",
                "active_menu": "monitoring",
                "alerts": alerts,
                "low_stock_alerts": alerts.filter(alert_type=Alert.AlertType.LOW_STOCK),
                "variance_alerts": alerts.filter(alert_type=Alert.AlertType.VARIANCE),
                "missing_submissions": alerts.filter(alert_type=Alert.AlertType.MISSING_SUBMISSION),
                "abnormal_changes": alerts.filter(alert_type=Alert.AlertType.ABNORMAL_CHANGE),
                "tank_watchlist": Tank.objects.select_related("terminal", "product").order_by("current_stock_liters")[:10],
            }
        )
        return context

