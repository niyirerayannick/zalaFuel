from django.urls import path

from .views import AdministrationOverviewView, DashboardRedirectView

app_name = "core"

urlpatterns = [
    path("", DashboardRedirectView.as_view(), name="root"),
    path("home/", DashboardRedirectView.as_view(), name="dashboard"),
    path("administration/", AdministrationOverviewView.as_view(), name="administration"),
]
