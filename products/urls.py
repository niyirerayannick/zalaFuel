from django.urls import path

from .views import ProductCreateView, ProductListView, SupplierListView

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("new/", ProductCreateView.as_view(), name="create"),
    path("suppliers/", SupplierListView.as_view(), name="suppliers"),
]

