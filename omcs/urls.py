from django.urls import path

from .views import OMCCreateView, OMCListView

app_name = "omcs"

urlpatterns = [
    path("", OMCListView.as_view(), name="list"),
    path("new/", OMCCreateView.as_view(), name="create"),
]

