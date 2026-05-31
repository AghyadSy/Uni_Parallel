import logging
import time
import uuid

from django.db import connection


logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware:
    """Captures request timing and query count outside view/service logic."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = str(uuid.uuid4())
        connection.force_debug_cursor = True
        start_queries = len(connection.queries)
        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        db_query_count = max(0, len(connection.queries) - start_queries)

        mode = getattr(request, "demo_mode", "after")
        response["X-Request-ID"] = request.request_id
        response["X-Response-Time-ms"] = str(duration_ms)
        response["X-Demo-Mode"] = mode
        response["X-DB-Query-Count"] = str(db_query_count)

        self._save_log(request, response.status_code, duration_ms, db_query_count, mode)
        return response

    def _save_log(self, request, status_code, duration_ms, db_query_count, mode):
        try:
            from apps.monitoring.models import PerformanceLog

            PerformanceLog.objects.create(
                request_id=request.request_id,
                method=request.method,
                path=request.path,
                mode=mode,
                status_code=status_code,
                duration_ms=duration_ms,
                db_query_count=db_query_count,
                user_identifier=self._user_identifier(request),
            )
        except Exception as exc:  # pragma: no cover - avoids blocking migrations/startup.
            logger.debug("Performance log skipped: %s", exc)

    def _user_identifier(self, request):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            return str(user.pk)
        return request.META.get("REMOTE_ADDR")
