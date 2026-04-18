from django.urls import path

from .views import ProductReceiptCreateView, ProductReceiptListView

app_name = "receipts"

urlpatterns = [
    path("", ProductReceiptListView.as_view(), name="list"),
    path("new/", ProductReceiptCreateView.as_view(), name="create"),
]

