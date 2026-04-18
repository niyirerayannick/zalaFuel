from django.urls import path

from .views import TankCreateView, TankEntryHistoryView, TankListView, TankStockEntryCreateView, TankUpdateView

app_name = "tanks"

urlpatterns = [
    path("", TankListView.as_view(), name="list"),
    path("new/", TankCreateView.as_view(), name="create"),
    path("<int:pk>/edit/", TankUpdateView.as_view(), name="update"),
    path("entries/new/", TankStockEntryCreateView.as_view(), name="entry-create"),
    path("entries/", TankEntryHistoryView.as_view(), name="entry-history"),
]

