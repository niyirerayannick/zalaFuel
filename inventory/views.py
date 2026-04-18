from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Count, F, Prefetch, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import TemplateView

from accounts.mixins import OperationsManageMixin
from accounts.station_access import (
    filter_fuel_sales_queryset_for_user,
    filter_inventory_records_queryset_for_user,
    filter_tanks_queryset_for_user,
    require_station_access,
    visible_stations,
)
from stations.models import Nozzle

from .forms import TankForm
from .models import FuelTank, InventoryRecord


class InventoryDashboardView(OperationsManageMixin, TemplateView):
    template_name = "inventory/index.html"
    extra_context = {"page_title": "Inventory", "active_menu": "inventory"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        tanks_qs = filter_tanks_queryset_for_user(FuelTank.objects.all(), user)
        totals = tanks_qs.aggregate(
            total_tanks=Count("id"),
            total_stock=Sum("current_volume_liters"),
            total_capacity=Sum("capacity_liters"),
        )
        fuel_breakdown = tanks_qs.values("fuel_type").annotate(
            stock=Sum("current_volume_liters"), capacity=Sum("capacity_liters")
        )
        fuel_map = {row["fuel_type"]: row for row in fuel_breakdown}
        petrol_stock = fuel_map.get("petrol", {}).get("stock") or 0
        petrol_capacity = fuel_map.get("petrol", {}).get("capacity") or 0
        diesel_stock = fuel_map.get("diesel", {}).get("stock") or 0
        diesel_capacity = fuel_map.get("diesel", {}).get("capacity") or 0
        low_tanks = tanks_qs.filter(
            low_level_threshold__gt=0, current_volume_liters__lte=F("low_level_threshold")
        ).select_related("station")

        records_base = filter_inventory_records_queryset_for_user(InventoryRecord.objects.all(), user)
        in_total = records_base.filter(change_type=InventoryRecord.ChangeType.IN).aggregate(s=Sum("quantity"))["s"] or 0
        out_total = records_base.filter(change_type=InventoryRecord.ChangeType.OUT).aggregate(s=Sum("quantity"))["s"] or 0
        adj_total = (
            records_base.filter(change_type=InventoryRecord.ChangeType.ADJUSTMENT).aggregate(s=Sum("quantity"))["s"] or 0
        )

        ctx.update(
            {
                "total_tanks": totals.get("total_tanks") or 0,
                "total_stock": totals.get("total_stock") or 0,
                "capacity": totals.get("total_capacity") or 0,
                "utilization": (
                    (totals.get("total_stock") or 0) / (totals.get("total_capacity") or 1) * 100
                    if totals.get("total_capacity")
                    else 0
                ),
                "fuel_breakdown": {
                    "petrol": {
                        "stock": petrol_stock,
                        "capacity": petrol_capacity,
                        "pct": (petrol_stock / petrol_capacity * 100) if petrol_capacity else 0,
                    },
                    "diesel": {
                        "stock": diesel_stock,
                        "capacity": diesel_capacity,
                        "pct": (diesel_stock / diesel_capacity * 100) if diesel_capacity else 0,
                    },
                },
                "low_tanks": low_tanks,
                "recent_records": records_base.select_related("tank", "tank__station").order_by("-created_at")[:10],
                "in_total": in_total,
                "out_total": out_total,
                "adj_total": adj_total,
            }
        )
        return ctx


class TankListView(OperationsManageMixin, TemplateView):
    template_name = "inventory/tanks.html"
    extra_context = {"page_title": "Tanks", "active_menu": "tanks"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        qs = filter_tanks_queryset_for_user(FuelTank.objects.select_related("station"), user)
        search = self.request.GET.get("search", "").strip()
        station_filter = self.request.GET.get("station")
        fuel_filter = self.request.GET.get("fuel_type")
        status_filter = self.request.GET.get("status")

        if search:
            qs = qs.filter(name__icontains=search)
        if station_filter:
            try:
                require_station_access(user, int(station_filter))
            except (PermissionDenied, TypeError, ValueError):
                qs = qs.none()
            else:
                qs = qs.filter(station_id=station_filter)
        if fuel_filter:
            qs = qs.filter(fuel_type=fuel_filter)
        if status_filter == "active":
            qs = qs.filter(is_active=True)
        elif status_filter == "inactive":
            qs = qs.filter(is_active=False)

        qs = qs.prefetch_related(
            Prefetch("nozzles", queryset=Nozzle.objects.select_related("pump").order_by("fuel_type")),
            Prefetch("inventory_records", queryset=InventoryRecord.objects.order_by("-created_at")),
        )

        totals = filter_tanks_queryset_for_user(FuelTank.objects.all(), user).aggregate(
            total_tanks=Count("id"),
            total_stock=Sum("current_volume_liters"),
            total_capacity=Sum("capacity_liters"),
            low_stock=Count(
                "id",
                filter=models.Q(low_level_threshold__gt=0, current_volume_liters__lte=F("low_level_threshold")),
            ),
        )
        ctx.update(
            {
                "tanks": qs,
                "stations": visible_stations(user),
                "search": search,
                "station_filter": station_filter or "",
                "fuel_filter": fuel_filter or "",
                "status_filter": status_filter or "",
                "kpi_total": totals.get("total_tanks") or 0,
                "kpi_stock": totals.get("total_stock") or 0,
                "kpi_low": totals.get("low_stock") or 0,
                "kpi_capacity_util": (
                    (totals.get("total_stock") or 0) / (totals.get("total_capacity") or 1) * 100
                    if totals.get("total_capacity")
                    else 0
                ),
            }
        )
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "inventory/_tanks_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class TankCreateView(OperationsManageMixin, View):
    template_name = "inventory/_tanks_modal_form.html"

    def get(self, request):
        form = TankForm(user=request.user)
        return render(request, self.template_name, {"form": form, "title": "Add Tank", "action": request.path})

    def post(self, request):
        form = TankForm(request.POST, user=request.user)
        if form.is_valid():
            tank = form.save(commit=False)
            try:
                require_station_access(request.user, tank.station_id)
            except PermissionDenied:
                return JsonResponse(
                    {"success": False, "non_field_errors": ["You cannot add a tank at this station."]},
                    status=403,
                )
            tank.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True})
            messages.success(request, "Tank created successfully.")
            return redirect("inventory:tanks")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors, "non_field_errors": form.non_field_errors()})
        return render(request, self.template_name, {"form": form, "title": "Add Tank", "action": request.path})


class TankUpdateView(OperationsManageMixin, View):
    template_name = "inventory/_tanks_modal_form.html"

    def get_object(self, pk):
        qs = filter_tanks_queryset_for_user(FuelTank.objects.all(), self.request.user)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        tank = self.get_object(pk)
        form = TankForm(instance=tank, user=request.user)
        return render(request, self.template_name, {"form": form, "title": "Edit Tank", "action": request.path})

    def post(self, request, pk):
        tank = self.get_object(pk)
        form = TankForm(request.POST, instance=tank, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            try:
                require_station_access(request.user, obj.station_id)
            except PermissionDenied:
                return JsonResponse(
                    {"success": False, "non_field_errors": ["You cannot assign this tank to that station."]},
                    status=403,
                )
            obj.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": True})
            messages.success(request, "Tank updated successfully.")
            return redirect("inventory:tanks")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "errors": form.errors, "non_field_errors": form.non_field_errors()})
        return render(request, self.template_name, {"form": form, "title": "Edit Tank", "action": request.path})


class TankDeleteView(OperationsManageMixin, View):
    template_name = "inventory/_tanks_confirm_delete.html"

    def get_object(self, pk):
        qs = filter_tanks_queryset_for_user(FuelTank.objects.all(), self.request.user)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        tank = self.get_object(pk)
        return render(request, self.template_name, {"tank": tank, "action": request.path})

    def post(self, request, pk):
        tank = self.get_object(pk)
        tank.delete()
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": True})
        messages.success(request, "Tank deleted.")
        return redirect("inventory:tanks")


class TankDetailView(OperationsManageMixin, TemplateView):
    template_name = "inventory/tank_detail.html"
    extra_context = {"page_title": "Tank Details", "active_menu": "tanks"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        pk = kwargs.get("pk")
        tank = get_object_or_404(
            filter_tanks_queryset_for_user(
                FuelTank.objects.select_related("station").prefetch_related(
                    Prefetch("nozzles", queryset=Nozzle.objects.select_related("pump").order_by("fuel_type")),
                    Prefetch("inventory_records", queryset=InventoryRecord.objects.order_by("-created_at")),
                ),
                user,
            ),
            pk=pk,
        )
        ctx["tank"] = tank
        ctx["recent_records"] = tank.inventory_records.all()[:10]
        ctx["recent_deliveries"] = (
            tank.deliveries.select_related("purchase_order", "purchase_order__supplier")
            .order_by("-delivery_date", "-created_at")[:5]
        )
        ctx["recent_sales"] = filter_fuel_sales_queryset_for_user(
            tank.sales.select_related("nozzle", "nozzle__pump", "shift"),
            user,
        ).order_by("-created_at")[:5]
        ctx["last_dip_reading"] = tank.readings.select_related("measured_by").order_by("-reading_time").first()
        return ctx
