from django.views.generic import TemplateView

from accounts.mixins import DashboardRoleMixin

from .services import dashboard_snapshot


class DashboardHomeView(DashboardRoleMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Dashboard",
                "active_menu": "dashboard",
                **dashboard_snapshot(),
            }
        )
        return context
