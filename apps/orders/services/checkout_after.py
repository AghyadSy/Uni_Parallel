import time
from decimal import Decimal

from django.db import OperationalError, close_old_connections, transaction

from apps.inventory.services import safe_decrease_stock
from apps.jobs.models import BackgroundJob
from apps.orders.models import Order, OrderItem
from apps.payments import services as payment_services
from apps.products.models import Product
from core.exceptions import PaymentFailed


def checkout(data, max_retries=5):
    for attempt in range(max_retries):
        try:
            return _checkout_once(data)
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == max_retries - 1:
                raise
            close_old_connections()
            time.sleep(0.05 * (attempt + 1))


def _checkout_once(data):
    start = time.perf_counter()
    with transaction.atomic():
        order = Order.objects.create(
            customer_name=data["customer_name"],
            status=Order.STATUS_PENDING,
            total_amount=Decimal("0.00"),
        )
        total = Decimal("0.00")

        for item in data["items"]:
            product = Product.objects.get(id=item["product_id"])
            quantity = int(item["quantity"])
            safe_decrease_stock(product.id, quantity)
            line_total = product.price * quantity
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
                total_price=line_total,
            )
            total += line_total

        if data.get("simulate_payment_failure"):
            raise PaymentFailed("Simulated payment failure.")

        payment_services.process_payment(order, total, simulate_failure=False)
        order.status = Order.STATUS_PAID
        order.total_amount = total
        order.save(update_fields=["status", "total_amount", "updated_at"])

    job = BackgroundJob.objects.create(
        type=BackgroundJob.TYPE_GENERATE_INVOICE,
        status=BackgroundJob.STATUS_PENDING,
        payload={"order_id": order.id, "customer_name": order.customer_name},
    )
    return {
        "order_id": order.id,
        "status": order.status,
        "payment_status": "success",
        "total_amount": str(order.total_amount),
        "invoice_generated_inside_request": False,
        "job_created": True,
        "job_id": job.id,
        "job_status": job.status,
        "checkout_time_ms": round((time.perf_counter() - start) * 1000, 2),
    }
