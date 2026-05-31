from apps.payments.models import Payment
from core.exceptions import PaymentFailed


def process_payment(order, amount, simulate_failure=False):
    if simulate_failure:
        raise PaymentFailed("Simulated payment failure.")
    return Payment.objects.create(order=order, amount=amount, status=Payment.STATUS_SUCCESS)


def record_failed_payment(order, amount, reason):
    return Payment.objects.create(
        order=order,
        amount=amount,
        status=Payment.STATUS_FAILED,
        failure_reason=reason,
    )
