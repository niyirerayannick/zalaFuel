from django.urls import path

from .views import (
    ProductCreateView,
    ProductDetailView,
    ProductListView,
    ProductToggleActiveView,
    ProductUpdateView,
    SupplierListView,
    SupplierCreateView,
    SupplierDetailView,
    SupplierUpdateView,
    SupplierToggleActiveView,
)

app_name = "products"

urlpatterns = [
    path("", ProductListView.as_view(), name="list"),
    path("new/", ProductCreateView.as_view(), name="create"),
    path("<int:pk>/", ProductDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", ProductUpdateView.as_view(), name="update"),
    path("<int:pk>/toggle/", ProductToggleActiveView.as_view(), name="toggle"),
    path("suppliers/", SupplierListView.as_view(), name="suppliers"),
    path("suppliers/new/", SupplierCreateView.as_view(), name="supplier_create"),
    path("suppliers/<int:pk>/", SupplierDetailView.as_view(), name="supplier_detail"),
    path("suppliers/<int:pk>/edit/", SupplierUpdateView.as_view(), name="supplier_update"),
    path("suppliers/<int:pk>/toggle/", SupplierToggleActiveView.as_view(), name="supplier_toggle"),
]

