from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import OperationsManageMixin
from accounts.station_access import (
    filter_delivery_receipts_queryset_for_user,
    filter_purchase_orders_queryset_for_user,
    filter_tanks_queryset_for_user,
    require_station_access,
    visible_stations,
)
from inventory.models import FuelTank

from .forms import DeliveryReceiptForm, FuelPurchaseOrderForm, SupplierForm
from .models import DeliveryReceipt, FuelPurchaseOrder, Supplier
from .services import post_supplier_delivery


class SupplierListView(OperationsManageMixin, TemplateView):
    template_name = "suppliers/index.html"
    extra_context = {"page_title": "Suppliers", "active_menu": "suppliers"}

    def get_queryset(self):
        search = self.request.GET.get("search", "").strip()
        suppliers = (
            Supplier.objects.annotate(
                po_count=Count("purchase_orders", distinct=True),
                received_volume=Sum(
                    "purchase_orders__deliveries__delivered_volume",
                    filter=Q(purchase_orders__deliveries__status=DeliveryReceipt.Status.RECEIVED),
                ),
            )
            .order_by("name")
        )
        if search:
            suppliers = suppliers.filter(
                Q(name__icontains=search)
                | Q(contact_person__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )
        return suppliers

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        suppliers = self.get_queryset()
        search = self.request.GET.get("search", "").strip()
        recent_deliveries = filter_delivery_receipts_queryset_for_user(
            DeliveryReceipt.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "purchase_order__station",
                "tank",
                "received_by",
            ),
            user,
        ).order_by("-created_at")[:8]
        po_base = filter_purchase_orders_queryset_for_user(FuelPurchaseOrder.objects.all(), user)
        del_base = filter_delivery_receipts_queryset_for_user(DeliveryReceipt.objects.all(), user)
        ctx.update(
            {
                "suppliers": suppliers,
                "filters": {"search": search},
                "recent_deliveries": recent_deliveries,
                "supplier_count": Supplier.objects.count(),
                "ordered_count": po_base.exclude(status=FuelPurchaseOrder.Status.DELIVERED).count(),
                "pending_receipts": del_base.filter(
                    status__in=[DeliveryReceipt.Status.DRAFT, DeliveryReceipt.Status.PENDING]
                ).count(),
                "received_volume": del_base.filter(status=DeliveryReceipt.Status.RECEIVED).aggregate(
                    total=Sum("delivered_volume")
                )["total"]
                or 0,
            }
        )
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "suppliers/_suppliers_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class SupplierCreateView(OperationsManageMixin, View):
    template_name = "suppliers/_supplier_modal_form.html"

    def get(self, request):
        form = SupplierForm()
        return render(request, self.template_name, {"form": form, "title": "New Supplier", "action": request.path})

    def post(self, request):
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True})
            messages.success(request, "Supplier created successfully.")
            return redirect("suppliers:list")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "errors": form.errors, "non_field_errors": form.non_field_errors()},
                status=400,
            )
        return render(request, self.template_name, {"form": form, "title": "New Supplier", "action": request.path}, status=400)


class SupplierUpdateView(OperationsManageMixin, View):
    template_name = "suppliers/_supplier_modal_form.html"

    def get_object(self, pk):
        return get_object_or_404(Supplier, pk=pk)

    def get(self, request, pk):
        supplier = self.get_object(pk)
        form = SupplierForm(instance=supplier)
        return render(request, self.template_name, {"form": form, "title": "Edit Supplier", "action": request.path})

    def post(self, request, pk):
        supplier = self.get_object(pk)
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True})
            messages.success(request, "Supplier updated successfully.")
            return redirect("suppliers:list")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse(
                {"success": False, "errors": form.errors, "non_field_errors": form.non_field_errors()},
                status=400,
            )
        return render(request, self.template_name, {"form": form, "title": "Edit Supplier", "action": request.path}, status=400)


class SupplierDeleteView(OperationsManageMixin, View):
    template_name = "suppliers/_supplier_confirm_delete.html"

    def get_object(self, pk):
        return get_object_or_404(Supplier, pk=pk)

    def get(self, request, pk):
        supplier = self.get_object(pk)
        return render(request, self.template_name, {"supplier": supplier, "action": request.path})

    def post(self, request, pk):
        supplier = self.get_object(pk)
        if supplier.purchase_orders.exists():
            message = "Suppliers with purchase orders should be retained for audit history."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "non_field_errors": [message]}, status=400)
            messages.error(request, message)
            return redirect("suppliers:list")
        supplier.delete()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        messages.success(request, "Supplier deleted successfully.")
        return redirect("suppliers:list")


class SupplierDetailView(OperationsManageMixin, TemplateView):
    template_name = "suppliers/detail.html"
    extra_context = {"page_title": "Supplier Details", "active_menu": "suppliers"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        supplier = get_object_or_404(
            Supplier.objects.prefetch_related(
                Prefetch(
                    "purchase_orders",
                    queryset=filter_purchase_orders_queryset_for_user(
                        FuelPurchaseOrder.objects.select_related("station"),
                        user,
                    ).order_by("-created_at"),
                ),
                Prefetch(
                    "purchase_orders__deliveries",
                    queryset=DeliveryReceipt.objects.select_related("tank", "received_by").order_by(
                        "-delivery_date", "-created_at"
                    ),
                ),
                "inventory_records",
            ),
            pk=kwargs["pk"],
        )
        deliveries = filter_delivery_receipts_queryset_for_user(
            DeliveryReceipt.objects.select_related("purchase_order", "tank", "received_by").filter(
                purchase_order__supplier=supplier
            ),
            user,
        ).order_by("-delivery_date", "-created_at")
        ctx.update(
            {
                "supplier": supplier,
                "deliveries": deliveries[:10],
                "purchase_orders": supplier.purchase_orders.all()[:10],
                "inventory_records": supplier.inventory_records.select_related("tank").all()[:10],
            }
        )
        return ctx


class PurchaseOrderListView(OperationsManageMixin, TemplateView):
    template_name = "suppliers/purchase_orders.html"
    extra_context = {"page_title": "Fuel Purchase Orders", "active_menu": "suppliers"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        search = self.request.GET.get("search", "").strip()
        status = self.request.GET.get("status", "").strip()
        station = self.request.GET.get("station", "").strip()
        orders = filter_purchase_orders_queryset_for_user(
            FuelPurchaseOrder.objects.select_related("supplier", "station")
            .annotate(
                received_volume=Sum(
                    "deliveries__delivered_volume",
                    filter=Q(deliveries__status=DeliveryReceipt.Status.RECEIVED),
                ),
                receipt_count=Count("deliveries"),
            )
            .order_by("-created_at"),
            user,
        )
        if search:
            orders = orders.filter(Q(reference__icontains=search) | Q(supplier__name__icontains=search))
        if status:
            orders = orders.filter(status=status)
        if station:
            try:
                require_station_access(user, int(station))
            except (PermissionDenied, TypeError, ValueError):
                orders = orders.none()
            else:
                orders = orders.filter(station_id=station)
        po_scope = filter_purchase_orders_queryset_for_user(FuelPurchaseOrder.objects.all(), user)
        ctx.update(
            {
                "orders": orders,
                "filters": {"search": search, "status": status, "station": station},
                "stations": visible_stations(user),
                "po_statuses": FuelPurchaseOrder.Status.choices,
                "draft_count": po_scope.filter(status=FuelPurchaseOrder.Status.DRAFT).count(),
                "ordered_count": po_scope.filter(status=FuelPurchaseOrder.Status.ORDERED).count(),
                "delivered_count": po_scope.filter(status=FuelPurchaseOrder.Status.DELIVERED).count(),
            }
        )
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "suppliers/_purchase_orders_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class PurchaseOrderCreateView(OperationsManageMixin, View):
    template_name = "suppliers/purchase_order_form.html"

    def get(self, request):
        form = FuelPurchaseOrderForm(initial={"status": FuelPurchaseOrder.Status.ORDERED}, user=request.user)
        if request.GET.get("partial") == "form":
            return render(
                request,
                "suppliers/_purchase_order_modal_form.html",
                {"form": form, "action": reverse("suppliers:purchase-orders-create")},
            )
        return render(request, self.template_name, {"form": form, "title": "New Purchase Order"})

    def post(self, request):
        form = FuelPurchaseOrderForm(request.POST, user=request.user)
        xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        if form.is_valid():
            po = form.save(commit=False)
            try:
                require_station_access(request.user, po.station_id)
            except PermissionDenied:
                if xhr:
                    return JsonResponse(
                        {
                            "success": False,
                            "non_field_errors": ["You cannot create a purchase order for this station."],
                        },
                        status=403,
                    )
                messages.error(request, "You cannot create a purchase order for this station.")
                return render(request, self.template_name, {"form": form, "title": "New Purchase Order"})
            po.save()
            if xhr:
                return JsonResponse({"success": True})
            messages.success(request, "Purchase order created successfully.")
            return redirect("suppliers:purchase-orders")
        if xhr:
            return JsonResponse(
                {"success": False, "errors": form.errors, "non_field_errors": form.non_field_errors()}
            )
        return render(request, self.template_name, {"form": form, "title": "New Purchase Order"})


class DeliveryReceiptListView(OperationsManageMixin, TemplateView):
    template_name = "suppliers/deliveries.html"
    extra_context = {"page_title": "Fuel Deliveries", "active_menu": "suppliers"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        search = self.request.GET.get("search", "").strip()
        status = self.request.GET.get("status", "").strip()
        deliveries = filter_delivery_receipts_queryset_for_user(
            DeliveryReceipt.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "purchase_order__station",
                "tank",
                "received_by",
            ),
            user,
        ).order_by("-delivery_date", "-created_at")
        if search:
            deliveries = deliveries.filter(
                Q(delivery_reference__icontains=search)
                | Q(purchase_order__reference__icontains=search)
                | Q(purchase_order__supplier__name__icontains=search)
            )
        if status:
            deliveries = deliveries.filter(status=status)
        del_scope = filter_delivery_receipts_queryset_for_user(DeliveryReceipt.objects.all(), user)
        ctx.update(
            {
                "deliveries": deliveries,
                "filters": {"search": search, "status": status},
                "delivery_statuses": DeliveryReceipt.Status.choices,
                "pending_count": del_scope.filter(
                    status__in=[DeliveryReceipt.Status.DRAFT, DeliveryReceipt.Status.PENDING]
                ).count(),
                "received_count": del_scope.filter(status=DeliveryReceipt.Status.RECEIVED).count(),
                "cancelled_count": del_scope.filter(status=DeliveryReceipt.Status.CANCELLED).count(),
                "received_volume": del_scope.filter(status=DeliveryReceipt.Status.RECEIVED).aggregate(
                    total=Sum("delivered_volume")
                )["total"]
                or 0,
            }
        )
        return ctx


class DeliveryReceiptCreateView(OperationsManageMixin, View):
    template_name = "suppliers/delivery_form.html"

    def get(self, request):
        initial = {}
        if request.GET.get("purchase_order"):
            initial["purchase_order"] = request.GET.get("purchase_order")
        if request.GET.get("tank"):
            initial["tank"] = request.GET.get("tank")
        form = DeliveryReceiptForm(initial=initial)
        return render(request, self.template_name, {"form": form, "title": "Record Delivery"})

    def post(self, request):
        form = DeliveryReceiptForm(request.POST, request.FILES)
        if form.is_valid():
            receipt = form.save(commit=False)
            try:
                require_station_access(request.user, receipt.purchase_order.station_id)
            except PermissionDenied:
                messages.error(request, "You cannot record a delivery for this station.")
                return render(request, self.template_name, {"form": form, "title": "Record Delivery"})
            receipt.received_by = request.user if receipt.status == DeliveryReceipt.Status.RECEIVED else None
            receipt.save()
            messages.success(request, "Delivery receipt saved. Post it when the fuel is physically received.")
            return redirect("suppliers:deliveries")
        return render(request, self.template_name, {"form": form, "title": "Record Delivery"})


class DeliveryReceiptPostView(OperationsManageMixin, View):
    def post(self, request, pk):
        qs = filter_delivery_receipts_queryset_for_user(DeliveryReceipt.objects.all(), request.user)
        receipt = get_object_or_404(qs, pk=pk)
        try:
            post_supplier_delivery(receipt_id=receipt.pk, actor=request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Delivery posted and tank inventory updated.")
        return redirect("suppliers:deliveries")


class PurchaseOrderTanksView(OperationsManageMixin, View):
    def get(self, request, pk):
        qs = filter_purchase_orders_queryset_for_user(FuelPurchaseOrder.objects.all(), request.user)
        purchase_order = get_object_or_404(qs, pk=pk)
        tanks = filter_tanks_queryset_for_user(
            FuelTank.objects.filter(
                station_id=purchase_order.station_id,
                fuel_type=purchase_order.fuel_type,
                is_active=True,
            ),
            request.user,
        ).order_by("name")
        return JsonResponse(
            {
                "results": [
                    {
                        "id": tank.pk,
                        "label": f"{tank.name} ({tank.current_volume_liters} / {tank.capacity_liters} L)",
                    }
                    for tank in tanks
                ]
            }
        )
