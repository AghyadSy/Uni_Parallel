import functools
import logging


logger = logging.getLogger(__name__)


def trace_operation(operation):
    """Decorator that records operation boundaries without polluting business services."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            request = _find_request(args, kwargs)
            _trace(request, operation, "start", f"{operation} started")
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                _trace(request, operation, "error", str(exc), {"exception": exc.__class__.__name__})
                raise
            _trace(request, operation, "complete", f"{operation} completed")
            return result

        return wrapper

    return decorator


def _find_request(args, kwargs):
    if "request" in kwargs:
        return kwargs["request"]
    for arg in args:
        if hasattr(arg, "request"):
            return arg.request
        if hasattr(arg, "META") and hasattr(arg, "method"):
            return arg
    return None


def _trace(request, operation, step, message, metadata=None):
    try:
        from apps.monitoring.models import TraceLog

        TraceLog.objects.create(
            request_id=getattr(request, "request_id", None),
            operation=operation,
            step=step,
            message=message,
            metadata=metadata or {},
        )
    except Exception as exc:  # pragma: no cover - tracing must never break the request.
        logger.debug("Trace log skipped: %s", exc)
