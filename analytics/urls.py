from django.urls import path

from .views import MarketShareDashboardView

app_name = "analytics"

urlpatterns = [
    path("", MarketShareDashboardView.as_view(), name="dashboard"),
]

