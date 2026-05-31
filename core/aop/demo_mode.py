from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone


class DemoModeMiddleware:
    """Stores before/after mode on the request and protects unsafe demos."""

    VALID_MODES = {"before", "after"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        mode = request.GET.get("mode", "after").lower()
        if mode not in self.VALID_MODES:
            mode = "after"
        request.demo_mode = mode

        if mode == "before" and not settings.ALLOW_UNSAFE_DEMO_MODE:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Unsafe before mode is disabled. Set ALLOW_UNSAFE_DEMO_MODE=True for educational demos.",
                    "code": "UNSAFE_DEMO_MODE_DISABLED",
                    "errors": {},
                    "meta": {
                        "request_id": getattr(request, "request_id", None),
                        "mode": mode,
                        "timestamp": timezone.now().isoformat(),
                    },
                },
                status=403,
            )

        return self.get_response(request)
