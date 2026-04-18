from django.urls import path

from .views import OMCSalesDashboardView, OMCSalesEntryCreateView, OMCSalesEntryUpdateView

app_name = "sales"

urlpatterns = [
    path("", OMCSalesDashboardView.as_view(), name="dashboard"),
    path("new/", OMCSalesEntryCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", OMCSalesEntryUpdateView.as_view(), name="update"),
]
