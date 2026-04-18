from django.urls import path

from .views import (
    TerminalActivityLogView,
    TerminalCreateView,
    TerminalDetailView,
    TerminalListView,
    TerminalStatusView,
)

app_name = "terminals"

urlpatterns = [
    path("", TerminalListView.as_view(), name="list"),
    path("new/", TerminalCreateView.as_view(), name="create"),
    path("status/", TerminalStatusView.as_view(), name="status"),
    path("activity/", TerminalActivityLogView.as_view(), name="activity"),
    path("<int:pk>/", TerminalDetailView.as_view(), name="detail"),
]

