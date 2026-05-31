import time
from decimal import Decimal

from django.utils import timezone

from apps.orders.models import Order
from apps.reports.models import DailySalesSummary


def process_daily_sales_before():
    start = time.perf_counter()
    orders = list(Order.objects.filter(status=Order.STATUS_PAID).order_by("id"))
    total_revenue = Decimal("0.00")

    for order in orders:
        total_revenue += order.total_amount
        if order.id % 1000 == 0:
            time.sleep(0.02)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    summary = DailySalesSummary.objects.create(
        date=timezone.localdate(),
        total_orders=len(orders),
        total_revenue=total_revenue,
        processed_in_chunks=False,
        chunk_size=0,
        duration_ms=duration_ms,
    )
    return {
        "summary_id": summary.id,
        "orders_processed": len(orders),
        "total_revenue": str(total_revenue),
        "processing_strategy": "load_all",
        "processed_in_chunks": False,
        "duration_ms": duration_ms,
    }


def process_daily_sales_after(chunk_size=500):
    start = time.perf_counter()
    total_orders = 0
    total_revenue = Decimal("0.00")
    last_id = 0

    while True:
        chunk = list(
            Order.objects.filter(status=Order.STATUS_PAID, id__gt=last_id)
            .order_by("id")
            .only("id", "total_amount")[:chunk_size]
        )
        if not chunk:
            break
        for order in chunk:
            total_revenue += order.total_amount
        total_orders += len(chunk)
        last_id = chunk[-1].id

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    summary = DailySalesSummary.objects.create(
        date=timezone.localdate(),
        total_orders=total_orders,
        total_revenue=total_revenue,
        processed_in_chunks=True,
        chunk_size=chunk_size,
        duration_ms=duration_ms,
    )
    return {
        "summary_id": summary.id,
        "orders_processed": total_orders,
        "total_revenue": str(total_revenue),
        "processing_strategy": "chunked",
        "chunk_size": chunk_size,
        "processed_in_chunks": True,
        "duration_ms": duration_ms,
    }
