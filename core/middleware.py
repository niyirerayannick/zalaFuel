from django.utils.deprecation import MiddlewareMixin


class ActiveStationMiddleware(MiddlewareMixin):
    """
    Attach the user's assigned station to request for quick access in views/templates.
    """

    def process_request(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            request.active_station = getattr(user, "assigned_station", None)
        else:
            request.active_station = None
