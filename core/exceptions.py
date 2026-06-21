from rest_framework import status
from rest_framework.views import exception_handler

from core.responses import api_error


class DemoError(Exception):
    code = "DEMO_ERROR"
    status_code = status.HTTP_400_BAD_REQUEST


class InsufficientStock(DemoError):
    code = "INSUFFICIENT_STOCK"


class PaymentFailed(DemoError):
    code = "PAYMENT_FAILED"
    status_code = status.HTTP_402_PAYMENT_REQUIRED


def custom_exception_handler(exc, context):
    request = context.get("request")
    if isinstance(exc, DemoError):
        return api_error(
            message=str(exc),
            code=exc.code,
            request=request,
            status=exc.status_code,
        )

    response = exception_handler(exc, context)
    if response is None:
        return None

    message = "Validation failed." if response.status_code == 400 else "Request failed."
    errors = response.data if isinstance(response.data, dict) else {"detail": response.data}
    return api_error(
        message=message,
        code=getattr(exc, "default_code", "API_ERROR"),
        errors=errors,
        request=request,
        status=response.status_code,
    )
