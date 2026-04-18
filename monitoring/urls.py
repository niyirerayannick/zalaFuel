from django.urls import path

from .views import MonitoringDashboardView

app_name = "monitoring"

urlpatterns = [
    path("", MonitoringDashboardView.as_view(), name="dashboard"),
]

