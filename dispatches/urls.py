from django.urls import path

from .views import DispatchCreateView, DispatchListView, DispatchUpdateView

app_name = "dispatches"

urlpatterns = [
    path("", DispatchListView.as_view(), name="list"),
    path("new/", DispatchCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", DispatchUpdateView.as_view(), name="update"),
]

