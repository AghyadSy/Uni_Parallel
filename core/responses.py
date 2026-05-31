from django.utils import timezone
from rest_framework.response import Response


def _request_meta(request=None, extra=None):
    meta = {
        "request_id": getattr(request, "request_id", None),
        "mode": getattr(request, "demo_mode", "after"),
        "timestamp": timezone.now().isoformat(),
    }
    if extra:
        meta.update(extra)
    return meta


def api_success(message="Operation completed successfully.", data=None, request=None, status=200, meta=None):
    return Response(
        {
            "success": True,
            "message": message,
            "data": data if data is not None else {},
            "meta": _request_meta(request, meta),
        },
        status=status,
    )


def api_error(message="Something went wrong.", code="ERROR", errors=None, request=None, status=400, meta=None):
    return Response(
        {
            "success": False,
            "message": message,
            "code": code,
            "errors": errors if errors is not None else {},
            "meta": _request_meta(request, meta),
        },
        status=status,
    )
