from django.urls import path

from .views import (
    InventoryDashboardView,
    TankListView,
    TankCreateView,
    TankUpdateView,
    TankDeleteView,
    TankDetailView,
)

app_name = "inventory"

urlpatterns = [
    path("", InventoryDashboardView.as_view(), name="dashboard"),
    path("tanks/", TankListView.as_view(), name="tanks"),
    path("tanks/create/", TankCreateView.as_view(), name="tanks-create"),
    path("tanks/<int:pk>/update/", TankUpdateView.as_view(), name="tanks-update"),
    path("tanks/<int:pk>/delete/", TankDeleteView.as_view(), name="tanks-delete"),
    path("tanks/<int:pk>/", TankDetailView.as_view(), name="tanks-detail"),
]
