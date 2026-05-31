import logging

from django.http import JsonResponse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(MiddlewareMixin):
    """Last-resort JSON formatter for unexpected API errors."""

    def process_exception(self, request, exception):
        logger.exception("Unhandled request error: %s", exception)
        return JsonResponse(
            {
                "success": False,
                "message": str(exception) or "Unexpected server error.",
                "code": "UNHANDLED_ERROR",
                "errors": {},
                "meta": {
                    "request_id": getattr(request, "request_id", None),
                    "mode": getattr(request, "demo_mode", "after"),
                    "timestamp": timezone.now().isoformat(),
                },
            },
            status=500,
        )
