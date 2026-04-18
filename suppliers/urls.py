from django.urls import path

from .views import (
    DeliveryReceiptCreateView,
    DeliveryReceiptListView,
    DeliveryReceiptPostView,
    PurchaseOrderCreateView,
    PurchaseOrderListView,
    PurchaseOrderTanksView,
    SupplierCreateView,
    SupplierDeleteView,
    SupplierDetailView,
    SupplierListView,
    SupplierUpdateView,
)

app_name = "suppliers"

urlpatterns = [
    path("", SupplierListView.as_view(), name="list"),
    path("create/", SupplierCreateView.as_view(), name="create"),
    path("<int:pk>/", SupplierDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", SupplierUpdateView.as_view(), name="update"),
    path("<int:pk>/delete/", SupplierDeleteView.as_view(), name="delete"),
    path("purchase-orders/", PurchaseOrderListView.as_view(), name="purchase-orders"),
    path("purchase-orders/create/", PurchaseOrderCreateView.as_view(), name="purchase-orders-create"),
    path("deliveries/", DeliveryReceiptListView.as_view(), name="deliveries"),
    path("deliveries/create/", DeliveryReceiptCreateView.as_view(), name="deliveries-create"),
    path("deliveries/<int:pk>/post/", DeliveryReceiptPostView.as_view(), name="deliveries-post"),
    path("api/purchase-orders/<int:pk>/tanks/", PurchaseOrderTanksView.as_view(), name="purchase-order-tanks"),
]
