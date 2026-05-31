import time
from decimal import Decimal
from threading import BrokenBarrierError

from django.conf import settings
from django.db.models import F

from apps.orders.models import Order, OrderItem
from apps.payments import services as payment_services
from apps.products.models import Product
from core.exceptions import InsufficientStock, PaymentFailed


def checkout(data, raise_payment_errors=True, pre_update_barrier=None):
    start = time.perf_counter()
    order = Order.objects.create(
        customer_name=data["customer_name"],
        status=Order.STATUS_PENDING,
        total_amount=Decimal("0.00"),
    )
    total = Decimal("0.00")

    for item in data["items"]:
        product = Product.objects.get(id=item["product_id"])
        quantity = int(item["quantity"])
        if product.stock < quantity:
            order.status = Order.STATUS_FAILED
            order.save(update_fields=["status", "updated_at"])
            raise InsufficientStock("Not enough stock.")

        if pre_update_barrier is not None:
            try:
                pre_update_barrier.wait(timeout=5)
            except BrokenBarrierError:
                pass

        time.sleep(0.05)
        Product.objects.filter(id=product.id).update(stock=F("stock") - quantity)
        line_total = product.price * quantity
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            total_price=line_total,
        )
        total += line_total

    order.total_amount = total

    if data.get("simulate_payment_failure"):
        reason = "Simulated payment failure after stock was decreased."
        payment_services.record_failed_payment(order, total, reason)
        order.status = Order.STATUS_FAILED
        order.save(update_fields=["status", "total_amount", "updated_at"])
        if raise_payment_errors:
            raise PaymentFailed("Payment failed after order and stock updates; before mode does not roll back.")
        return _result(order, start, invoice_generated=True, payment_status="failed")

    payment_services.process_payment(order, total, simulate_failure=False)
    order.status = Order.STATUS_PAID
    order.save(update_fields=["status", "total_amount", "updated_at"])

    time.sleep(settings.DEMO_INVOICE_DELAY_SECONDS)
    return _result(order, start, invoice_generated=True, payment_status="success")


def _result(order, start, invoice_generated, payment_status):
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_status": payment_status,
        "total_amount": str(order.total_amount),
        "invoice_generated_inside_request": invoice_generated,
        "checkout_time_ms": round((time.perf_counter() - start) * 1000, 2),
    }
