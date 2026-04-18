# Route Module Views
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Avg, Q, Sum
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from accounts.rbac import can_access_fleet, can_manage_fleet
from .forms import RouteForm
from .models import Route
from transport.trips.models import Trip


class StaffRequiredMixin(UserPassesTestMixin):
    """Mixin to require staff access level"""

    def test_func(self):
        return self.request.user.is_authenticated and can_access_fleet(self.request.user)


class FleetWriteRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and can_manage_fleet(self.request.user)


class RouteListView(StaffRequiredMixin, ListView):
    model = Route
    template_name = 'transport/routes/list.html'
    context_object_name = 'routes'
    paginate_by = 20

    def get_template_names(self):
        if self.request.GET.get("partial") == "list":
            return ["transport/routes/_list_content.html"]
        return [self.template_name]

    def get_queryset(self):
        queryset = Route.objects.all()
        search = self.request.GET.get('search')

        if search:
            queryset = queryset.filter(
                Q(origin__icontains=search) |
                Q(destination__icontains=search)
            )

        return queryset.order_by('origin', 'destination')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_routes = Route.objects.all()
        context['total_routes'] = all_routes.count()
        context['active_routes'] = all_routes.filter(is_active=True).count()
        context['total_distance'] = all_routes.aggregate(total=Sum('distance_km'))['total'] or 0
        context['avg_distance'] = all_routes.aggregate(avg_dist=Avg('distance_km'))['avg_dist'] or 0
        context['search_query'] = self.request.GET.get('search', '')
        context['can_manage_fleet'] = can_manage_fleet(self.request.user)
        return context


class RouteDetailView(StaffRequiredMixin, DetailView):
    model = Route
    template_name = 'transport/routes/detail.html'
    context_object_name = 'route'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        route = self.get_object()
        tab = self.request.GET.get('tab', 'overview')
        context['current_tab'] = tab
        context['recent_trips'] = Trip.objects.filter(
            route=route
        ).select_related('customer', 'vehicle', 'driver').order_by('-created_at')[:10]

        route_trips = Trip.objects.filter(route=route)
        completed_trips = route_trips.filter(status__in=['DELIVERED', 'CLOSED'])

        context['route_analytics'] = {
            'total_trips': route_trips.count(),
            'completed_trips': completed_trips.count(),
            'total_revenue': completed_trips.aggregate(total=Sum('revenue'))['total'] or 0,
            'avg_trip_duration': '4h 30m',
            'utilization_rate': 78,
            'profitability_score': 85,
        }
        context['can_manage_fleet'] = can_manage_fleet(self.request.user)
        return context


class RouteCreateView(FleetWriteRequiredMixin, CreateView):
    model = Route
    form_class = RouteForm
    template_name = 'transport/routes/create.html'
    success_url = reverse_lazy('transport:routes:list')

    def _is_ajax(self):
        return self.request.headers.get("x-requested-with") == "XMLHttpRequest"

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["transport/routes/_modal_form.html"]
        return [self.template_name]

    def form_valid(self, form):
        if self._is_ajax():
            self.object = form.save()
            return JsonResponse({
                "success": True,
                "id": self.object.pk,
                "detail_url": reverse_lazy('transport:routes:detail', kwargs={'pk': self.object.pk}),
                "message": "Route created successfully!",
            })
        messages.success(self.request, f'Route {form.instance.origin} -> {form.instance.destination} created successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        if self._is_ajax():
            return JsonResponse({
                "success": False,
                "errors": form.errors,
                "non_field_errors": form.non_field_errors(),
            }, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cancel_url"] = reverse_lazy('transport:routes:list')
        context["back_url"] = reverse_lazy('transport:routes:list')
        return context


class RouteUpdateView(FleetWriteRequiredMixin, UpdateView):
    model = Route
    form_class = RouteForm
    template_name = 'transport/routes/edit.html'

    def _is_ajax(self):
        return self.request.headers.get("x-requested-with") == "XMLHttpRequest"

    def get_template_names(self):
        if self.request.GET.get("partial") == "form":
            return ["transport/routes/_modal_form.html"]
        return [self.template_name]

    def get_success_url(self):
        return reverse_lazy('transport:routes:detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        if self._is_ajax():
            self.object = form.save()
            return JsonResponse({
                "success": True,
                "id": self.object.pk,
                "detail_url": reverse_lazy('transport:routes:detail', kwargs={'pk': self.object.pk}),
                "message": "Route updated successfully!",
            })
        messages.success(self.request, 'Route updated successfully!')
        return super().form_valid(form)

    def form_invalid(self, form):
        if self._is_ajax():
            return JsonResponse({
                "success": False,
                "errors": form.errors,
                "non_field_errors": form.non_field_errors(),
            }, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["route"] = self.object
        context["cancel_url"] = reverse_lazy('transport:routes:detail', kwargs={'pk': self.object.pk})
        context["back_url"] = reverse_lazy('transport:routes:detail', kwargs={'pk': self.object.pk})
        return context
