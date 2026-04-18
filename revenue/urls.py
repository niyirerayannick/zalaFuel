from django.urls import path

from .views import RevenueDashboardView, RevenueEntryCreateView, RevenueEntryUpdateView

app_name = "revenue"

urlpatterns = [
    path("", RevenueDashboardView.as_view(), name="dashboard"),
    path("new/", RevenueEntryCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", RevenueEntryUpdateView.as_view(), name="update"),
]

