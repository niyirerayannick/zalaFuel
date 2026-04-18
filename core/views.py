from django.views.generic import TemplateView
from django.views.generic.base import RedirectView

from accounts.mixins import AdminMixin


class DashboardRedirectView(RedirectView):
    pattern_name = "dashboard:home"
    permanent = False


class AdministrationOverviewView(AdminMixin, TemplateView):
    template_name = "core/administration.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Administration",
                "active_menu": "administration",
                "admin_modules": [
                    {"title": "Users", "href": "accounts:user-list", "description": "Manage access, roles, and audit readiness."},
                    {"title": "Products", "href": "products:list", "description": "Maintain petroleum product master data and defaults."},
                    {"title": "Terminals", "href": "terminals:list", "description": "Control terminal master records and operating status."},
                    {"title": "Tanks", "href": "tanks:list", "description": "Maintain tank capacity, thresholds, and utilization."},
                    {"title": "OMCs", "href": "omcs:list", "description": "Keep OMC profiles and market participants current."},
                    {"title": "System Settings", "href": "accounts:system-settings", "description": "Branding, communication, and platform defaults."},
                    {"title": "Report Templates", "href": "reports:dashboard", "description": "Configure standard exports and reporting outputs."},
                ],
            }
        )
        return context
