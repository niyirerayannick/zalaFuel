from django.urls import path

from .views import OMCCreateView, OMCListView, OMCUpdateView

app_name = "omcs"

urlpatterns = [
    path("", OMCListView.as_view(), name="list"),
    path("new/", OMCCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", OMCUpdateView.as_view(), name="update"),
]

