import logging
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, TemplateView

from accounts.mixins import OperationsRoleMixin
from accounts.models import SystemSettings
from accounts.station_access import (
    filter_fuel_sales_queryset_for_user,
    filter_shifts_queryset_for_user,
    require_station_access,
    user_can_access_shift,
    user_can_close_shift,
    user_can_open_shift_for,
    visible_stations,
)
from stations.models import Nozzle, Pump

from .forms import ShiftCloseForm, ShiftOpenForm
from .models import Customer, FuelSale, PumpReading, ShiftSession
from .selectors import station_attendants
from .services import post_sale_and_update_inventory, shift_sales_summary

logger = logging.getLogger(__name__)

MONEY_QUANT = Decimal("0.01")


def quantize_2(value):
    return Decimal(value or 0).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


class POSView(OperationsRoleMixin, TemplateView):
    template_name = "sales/pos.html"
    extra_context = {"page_title": "Sales", "active_menu": "sales"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        user_display = (
            getattr(user, "full_name", "")
            or getattr(user, "get_full_name", lambda: "")()
            or getattr(user, "email", "")
            or str(user)
        )
        stations = visible_stations(user)
        active_shift = (
            ShiftSession.objects.filter(attendant=user, status=ShiftSession.Status.OPEN)
            .select_related("station", "attendant")
            .order_by("-opened_at")
            .first()
        )

        qs = filter_fuel_sales_queryset_for_user(
            FuelSale.objects.select_related(
                "shift", "shift__station", "attendant", "nozzle", "nozzle__pump", "nozzle__pump__station"
            ),
            user,
        ).order_by("-created_at")

        station_filter = self.request.GET.get("station")
        pay_filter = self.request.GET.get("payment_method")
        attendant_filter = self.request.GET.get("attendant")
        shift_filter = self.request.GET.get("shift")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")
        search = self.request.GET.get("search", "").strip()

        if station_filter:
            try:
                require_station_access(user, int(station_filter))
            except (PermissionDenied, TypeError, ValueError):
                qs = qs.none()
            else:
                qs = qs.filter(shift__station_id=station_filter)
        if pay_filter:
            qs = qs.filter(payment_method=pay_filter)
        if attendant_filter:
            qs = qs.filter(attendant_id=attendant_filter)
        if shift_filter:
            qs = qs.filter(shift_id=shift_filter)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        if search:
            qs = qs.filter(
                Q(customer_name__icontains=search) | Q(id__icontains=search) | Q(receipt_number__icontains=search)
            )

        today = timezone.now().date()
        today_sales = qs.filter(created_at__date=today)
        shifts_qs = filter_shifts_queryset_for_user(
            ShiftSession.objects.select_related("station", "attendant"), user
        )
        open_shifts = shifts_qs.filter(status=ShiftSession.Status.OPEN).order_by("-opened_at")
        if active_shift is None:
            active_shift = open_shifts.first()
        suspended_sales = []
        ctx.update(
            {
                "stations": stations,
                "user_display": user_display,
                "credit_customers": Customer.objects.filter(is_credit_allowed=True).order_by("name"),
                "active_shift": active_shift,
                "open_shifts": open_shifts,
                "attendants": shifts_qs.values("attendant_id", "attendant__full_name")
                .distinct()
                .order_by("attendant__full_name"),
                "shifts": shifts_qs.order_by("-opened_at")[:200],
                "form_payment_methods": FuelSale.PaymentMethod.choices,
                "sales": qs,
                "suspended_sales": suspended_sales,
                "filters": {
                    "station": station_filter or "",
                    "payment_method": pay_filter or "",
                    "attendant": attendant_filter or "",
                    "shift": shift_filter or "",
                    "date_from": date_from or "",
                    "date_to": date_to or "",
                    "search": search or "",
                },
                "kpi_sales_today": today_sales.aggregate(s=Sum("total_amount"))["s"] or 0,
                "kpi_liters_today": today_sales.aggregate(s=Sum("volume_liters"))["s"] or 0,
                "kpi_revenue_today": today_sales.aggregate(s=Sum("total_amount"))["s"] or 0,
                "kpi_credit_today": today_sales.filter(payment_method=FuelSale.PaymentMethod.CREDIT).aggregate(s=Sum("total_amount"))["s"]
                or 0,
                "kpi_active_shifts": shifts_qs.filter(status=ShiftSession.Status.OPEN).count(),
                "kpi_active_pumps": (
                    Pump.objects.filter(is_active=True, station_id__in=stations.values_list("pk", flat=True)).count()
                    if stations.exists()
                    else 0
                ),
                "kpi_suspended": len(suspended_sales),
                "kpi_shift_cash": today_sales.filter(payment_method=FuelSale.PaymentMethod.CASH).aggregate(s=Sum("total_amount"))["s"]
                or 0,
                "now": timezone.now(),
            }
        )
        return ctx

    def render_to_response(self, context, **response_kwargs):
        partial = self.request.GET.get("partial")
        if partial == "transactions":
            return render(self.request, "sales/_pos_transactions.html", context)
        if partial == "suspended":
            return render(self.request, "sales/_pos_suspended.html", context)
        return super().render_to_response(context, **response_kwargs)


class ShiftListView(OperationsRoleMixin, TemplateView):
    template_name = "sales/shifts.html"
    extra_context = {"page_title": "Shifts", "active_menu": "shifts"}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        station_filter = self.request.GET.get("station")
        status_filter = self.request.GET.get("status")
        shift_type_filter = self.request.GET.get("shift_type")
        sales_by_shift = FuelSale.objects.filter(shift=models.OuterRef("pk")).values("shift")
        shifts_base = filter_shifts_queryset_for_user(
            ShiftSession.objects.select_related("station", "attendant"),
            user,
        )
        shifts = shifts_base.annotate(
            readings_count=models.Count("pump_readings", distinct=True),
            sales_count=models.Subquery(
                sales_by_shift.annotate(count=models.Count("id")).values("count")[:1],
                output_field=models.IntegerField(),
            ),
            actual_sales=models.Subquery(
                sales_by_shift.annotate(total=models.Sum("total_amount")).values("total")[:1],
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            ),
            actual_liters=models.Subquery(
                sales_by_shift.annotate(total=models.Sum("volume_liters")).values("total")[:1],
                output_field=models.DecimalField(max_digits=12, decimal_places=2),
            ),
        ).order_by("-opened_at")
        if station_filter:
            try:
                require_station_access(user, int(station_filter))
            except (PermissionDenied, TypeError, ValueError):
                shifts = shifts.none()
            else:
                shifts = shifts.filter(station_id=station_filter)
        if status_filter:
            shifts = shifts.filter(status=status_filter)
        if shift_type_filter:
            shifts = shifts.filter(shift_type=shift_type_filter)

        today = timezone.now().date()
        sales_today = filter_fuel_sales_queryset_for_user(
            FuelSale.objects.filter(created_at__date=today),
            user,
        )
        ctx["shifts"] = shifts
        ctx["open_form"] = ShiftOpenForm(user=user)
        ctx["stations"] = visible_stations(user)
        ctx["filters"] = {
            "station": station_filter or "",
            "status": status_filter or "",
            "shift_type": shift_type_filter or "",
        }
        ctx["shift_type_choices"] = ShiftSession.ShiftType.choices
        ctx["kpi_active"] = shifts_base.filter(status=ShiftSession.Status.OPEN).count()
        ctx["kpi_sales_today"] = sales_today.aggregate(s=models.Sum("total_amount"))["s"] or 0
        ctx["kpi_liters_today"] = sales_today.aggregate(s=models.Sum("volume_liters"))["s"] or 0
        ctx["kpi_attendants"] = (
            shifts.filter(status=ShiftSession.Status.OPEN).values("attendant").distinct().count()
        )
        return ctx

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get("partial") == "list":
            return render(self.request, "sales/_shifts_list_content.html", context)
        return super().render_to_response(context, **response_kwargs)


class ShiftDetailView(OperationsRoleMixin, DetailView):
    model = ShiftSession
    template_name = "sales/shift_detail.html"
    context_object_name = "shift"

    def get_queryset(self):
        return filter_shifts_queryset_for_user(
            ShiftSession.objects.select_related("station", "attendant"),
            self.request.user,
        )

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not user_can_access_shift(self.request.user, obj):
            raise PermissionDenied("You cannot view this shift.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        shift = self.object
        ctx["sales"] = shift.sales.select_related("nozzle", "nozzle__pump", "attendant")
        ctx["summary"] = shift_sales_summary(shift)
        return ctx


class ShiftOpenView(OperationsRoleMixin, View):
    template_name = "sales/_shift_modal_form.html"

    def get_opening_reading(self, nozzle):
        latest_sale = (
            FuelSale.objects.filter(nozzle=nozzle, closing_meter__isnull=False)
            .order_by("-created_at", "-id")
            .only("closing_meter")
            .first()
        )
        if latest_sale:
            return latest_sale.closing_meter
        latest_reading = (
            PumpReading.objects.filter(nozzle=nozzle, closing_reading__isnull=False)
            .order_by("-created_at", "-id")
            .only("closing_reading")
            .first()
        )
        if latest_reading:
            return latest_reading.closing_reading
        return nozzle.meter_start or Decimal("0")

    def build_pump_readings(self, shift, post_data):
        readings = []
        errors = {}
        nozzles = (
            Nozzle.objects.filter(pump__station=shift.station, is_active=True)
            .select_related("pump")
            .order_by("pump__label", "fuel_type")
        )

        for nozzle in nozzles:
            field_name = f"opening_reading_{nozzle.pk}"
            raw_value = (post_data.get(field_name) or "").strip()
            if raw_value:
                try:
                    opening_reading = Decimal(raw_value)
                except Exception:
                    errors[field_name] = ["Enter a valid opening reading."]
                    continue
                if opening_reading < 0:
                    errors[field_name] = ["Opening reading cannot be negative."]
                    continue
            else:
                opening_reading = self.get_opening_reading(nozzle)
            readings.append(PumpReading(shift=shift, nozzle=nozzle, opening_reading=opening_reading))

        return readings, errors

    def get(self, request):
        form = ShiftOpenForm(user=request.user)
        attendant_name = None
        if hasattr(request.user, "full_name"):
            attendant_name = request.user.full_name or ""
        if not attendant_name and hasattr(request.user, "get_full_name"):
            attendant_name = request.user.get_full_name() or ""
        if not attendant_name:
            attendant_name = request.user.username
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "title": "Open Shift",
                "attendant_name": attendant_name,
            },
        )

    def post(self, request):
        form = ShiftOpenForm(request.POST, user=request.user)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.opened_by = request.user
            shift.status = ShiftSession.Status.OPEN
            if not user_can_open_shift_for(
                request.user, station=shift.station, attendant=shift.attendant
            ):
                return JsonResponse(
                    {"success": False, "error": "You are not allowed to open this shift."},
                    status=403,
                )
            with transaction.atomic():
                try:
                    shift.full_clean()
                except ValidationError as exc:
                    transaction.set_rollback(True)
                    return JsonResponse(
                        {"success": False, "errors": getattr(exc, "message_dict", {}), "error": str(exc)},
                        status=400,
                    )
                shift.save()
                readings, reading_errors = self.build_pump_readings(shift, request.POST)
                if reading_errors:
                    transaction.set_rollback(True)
                    return JsonResponse({"success": False, "errors": reading_errors}, status=400)
                PumpReading.objects.bulk_create(readings)
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "errors": form.errors}, status=400)


class StationNozzleReadingsView(OperationsRoleMixin, View):
    def get_opening_reading(self, nozzle):
        latest_sale = (
            FuelSale.objects.filter(nozzle=nozzle, closing_meter__isnull=False)
            .order_by("-created_at", "-id")
            .only("closing_meter")
            .first()
        )
        if latest_sale:
            return latest_sale.closing_meter, "Latest closing sale"
        latest_reading = (
            PumpReading.objects.filter(nozzle=nozzle, closing_reading__isnull=False)
            .order_by("-created_at", "-id")
            .only("closing_reading")
            .first()
        )
        if latest_reading:
            return latest_reading.closing_reading, "Latest closed reading"
        return nozzle.meter_start or Decimal("0"), "Nozzle start"

    def get(self, request):
        station_id = request.GET.get("station")
        if not station_id:
            return JsonResponse({"results": []})
        try:
            require_station_access(request.user, int(station_id))
        except (PermissionDenied, TypeError, ValueError):
            return JsonResponse({"results": [], "error": "Forbidden"}, status=403)
        nozzles = (
            Nozzle.objects.filter(pump__station_id=station_id, is_active=True)
            .select_related("pump")
            .order_by("pump__label", "fuel_type")
        )
        data = []
        for nozzle in nozzles:
            opening_reading, source = self.get_opening_reading(nozzle)
            data.append(
                {
                    "id": nozzle.pk,
                    "label": f"{nozzle.pump.label} - {nozzle.get_fuel_type_display()}",
                    "opening_reading": f"{Decimal(opening_reading or 0):.2f}",
                    "source": source,
                }
            )
        return JsonResponse({"results": data})


class StationAttendantsView(OperationsRoleMixin, View):
    def get(self, request):
        station_id = request.GET.get("station")
        if not station_id:
            return JsonResponse({"results": [], "empty_message": "Select a station."})
        try:
            require_station_access(request.user, int(station_id))
        except (PermissionDenied, TypeError, ValueError):
            return JsonResponse({"results": [], "empty_message": "Forbidden"}, status=403)
        attendants = station_attendants(station_id)
        data = [
            {
                "id": str(attendant.pk),
                "label": attendant.full_name or attendant.email,
            }
            for attendant in attendants
        ]
        return JsonResponse(
            {
                "results": data,
                "empty_message": "No active attendants are assigned to this station.",
            }
        )


class ShiftCloseView(OperationsRoleMixin, View):
    template_name = "sales/_shift_modal_form.html"

    def get_shift(self, pk):
        qs = filter_shifts_queryset_for_user(ShiftSession.objects.all(), self.request.user)
        return get_object_or_404(qs, pk=pk)

    def get(self, request, pk):
        shift = self.get_shift(pk)
        if not user_can_close_shift(request.user, shift):
            raise PermissionDenied("You cannot close this shift.")
        form = ShiftCloseForm(instance=shift)
        return render(
            request,
            self.template_name,
            {"form": form, "title": "Close Shift", "summary": shift_sales_summary(shift)},
        )

    def post(self, request, pk):
        shift = self.get_shift(pk)
        if not user_can_close_shift(request.user, shift):
            return JsonResponse({"success": False, "error": "You cannot close this shift."}, status=403)
        form = ShiftCloseForm(request.POST, instance=shift)
        if form.is_valid():
            closing_cash = form.cleaned_data.get("closing_cash")
            closing_note = form.cleaned_data.get("closing_note") or ""
            try:
                shift.close(closing_cash=closing_cash, closed_by=request.user, closing_note=closing_note)
            except ValidationError as exc:
                return JsonResponse(
                    {"success": False, "errors": getattr(exc, "message_dict", {}), "error": str(exc)},
                    status=400,
                )
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "errors": form.errors}, status=400)


class PumpChoicesView(OperationsRoleMixin, View):
    def get(self, request):
        station_id = request.GET.get("station")
        if not station_id:
            return JsonResponse({"results": []})
        try:
            require_station_access(request.user, int(station_id))
        except (PermissionDenied, TypeError, ValueError):
            return JsonResponse({"results": []}, status=403)
        pumps = Pump.objects.filter(station_id=station_id, is_active=True).order_by("label")
        data = [{"id": p.id, "label": p.label} for p in pumps]
        return JsonResponse({"results": data})


class NozzleChoicesView(OperationsRoleMixin, View):
    def get(self, request):
        pump_id = request.GET.get("pump")
        if not pump_id:
            return JsonResponse({"results": []})
        pump = get_object_or_404(Pump.objects.select_related("station"), pk=pump_id)
        try:
            require_station_access(request.user, pump.station_id)
        except PermissionDenied:
            return JsonResponse({"results": []}, status=403)
        nozzles = Nozzle.objects.filter(pump_id=pump_id, is_active=True).order_by("fuel_type")
        data = [{"id": n.id, "label": f"{n.get_fuel_type_display()}"} for n in nozzles]
        return JsonResponse({"results": data})


class NozzleTankInfoView(OperationsRoleMixin, View):
    def get(self, request, nozzle_id):
        nozzle = get_object_or_404(Nozzle.objects.select_related("tank", "pump", "pump__station"), pk=nozzle_id)
        try:
            require_station_access(request.user, nozzle.pump.station_id)
        except PermissionDenied:
            return JsonResponse({"error": "Forbidden"}, status=403)
        tank = nozzle.tank
        if not tank:
            return JsonResponse({"error": "No tank linked"}, status=400)
        latest_sale = (
            FuelSale.objects.filter(nozzle=nozzle, closing_meter__isnull=False)
            .order_by("-created_at", "-pk")
            .only("closing_meter")
            .first()
        )
        opening_meter = latest_sale.closing_meter if latest_sale else nozzle.meter_start
        settings = SystemSettings.get_settings()
        unit_price = 0
        if settings:
            unit_price = (
                settings.diesel_unit_price if nozzle.fuel_type == Nozzle.FuelType.DIESEL else settings.petrol_unit_price
            )
        return JsonResponse(
            {
                "tank": tank.name,
                "fuel_type": nozzle.get_fuel_type_display(),
                "current_stock": float(tank.current_volume_liters),
                "capacity": float(tank.capacity_liters),
                "low_level_threshold": float(tank.low_level_threshold),
                "opening_meter": float(opening_meter or 0),
                "opening_meter_source": "latest_closing" if latest_sale else "nozzle_start",
                "unit_price": float(unit_price or 0),
            }
        )


class CreateSaleView(OperationsRoleMixin, View):
    """Create a new fuel sale attached to the active shift."""

    def post(self, request):
        try:
            station_id = request.POST.get("station")
            shift_id = request.POST.get("shift")
            nozzle_id = request.POST.get("nozzle")
            closing = quantize_2(request.POST.get("closing_meter", "0"))
            payment_method = request.POST.get("payment_method", FuelSale.PaymentMethod.CASH)
            customer_name = request.POST.get("customer_name", "").strip()
            receipt_number = request.POST.get("receipt_number", "").strip()
            customer_id = request.POST.get("customer")
        except (ValueError, TypeError) as exc:
            return JsonResponse(
                {"success": False, "error": f"Invalid input format: {str(exc)}"},
                status=400,
            )

        shifts_qs = filter_shifts_queryset_for_user(
            ShiftSession.objects.select_related("station", "attendant").filter(status=ShiftSession.Status.OPEN),
            request.user,
        )
        selected_shift = None
        if shift_id:
            selected_shift = shifts_qs.filter(pk=shift_id).first()
            if selected_shift is None:
                return JsonResponse(
                    {"success": False, "error": "Selected shift is invalid or no longer open."},
                    status=400,
                )
        else:
            selected_shift = (
                shifts_qs.filter(attendant=request.user).order_by("-opened_at").first()
                or shifts_qs.order_by("-opened_at").first()
            )

        if not selected_shift:
            return JsonResponse(
                {
                    "success": False,
                    "error": "No open shift found. Please open a shift before recording sales.",
                },
                status=400,
            )

        if station_id and str(selected_shift.station_id) != str(station_id):
            return JsonResponse(
                {"success": False, "error": "Selected station does not match the selected shift."},
                status=400,
            )

        try:
            sale, tank = post_sale_and_update_inventory(
                shift=selected_shift,
                attendant=selected_shift.attendant or request.user,
                nozzle_id=nozzle_id,
                closing_meter=closing,
                payment_method=payment_method,
                customer_id=customer_id or None,
                customer_name=customer_name,
                receipt_number=receipt_number,
            )
        except ValidationError as exc:
            return JsonResponse(
                {"success": False, "error": "; ".join(exc.messages)},
                status=400,
            )
        except ObjectDoesNotExist:
            return JsonResponse(
                {"success": False, "error": "Selected sale customer or nozzle could not be found."},
                status=400,
            )
        except Exception:
            logger.exception("CreateSaleView failed for user=%s", getattr(request.user, "pk", None))
            return JsonResponse(
                {"success": False, "error": "Could not record the sale. Please try again or contact support."},
                status=500,
            )

        messages.success(request, f"Sale recorded successfully. {sale.volume_liters}L sold.")
        return JsonResponse(
            {
                "success": True,
                "sale_id": sale.id,
                "volume": float(sale.volume_liters),
                "total": float(sale.total_amount),
                "tank_id": tank.id,
                "tank_balance": float(tank.current_volume_liters),
                "message": (
                    f"{sale.volume_liters}L of {sale.nozzle.get_fuel_type_display()} sold for {sale.total_amount}. "
                    f"Tank balance is now {tank.current_volume_liters}L."
                ),
            }
        )
