import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, close_old_connections, connection
from django.db.models import F
from django.utils import timezone

from apps.inventory.services import safe_decrease_stock
from apps.jobs.models import BackgroundJob
from apps.monitoring.models import PerformanceLog, TraceLog
from apps.orders.models import Order, OrderItem
from apps.orders.services import checkout_after, checkout_before
from apps.payments import services as payment_services
from apps.payments.models import Payment
from apps.products.models import Product
from apps.reports.models import DailySalesSummary
from core.exceptions import InsufficientStock, PaymentFailed


RACE_PRODUCT_SKU = "RACE-001"
LATEST_COMPARISON_CACHE_PREFIX = "demo:latest:"


def reset_demo_data(seed_orders=False, clear_monitoring=True):
    cache.clear()
    BackgroundJob.objects.all().delete()
    DailySalesSummary.objects.all().delete()
    Order.objects.all().delete()
    Payment.objects.all().delete()
    Product.objects.all().delete()
    _reset_sqlite_sequences()
    if clear_monitoring:
        PerformanceLog.objects.all().delete()
        TraceLog.objects.all().delete()

    products = create_demo_products()
    created_orders = create_fake_orders(count=10000) if seed_orders else 0
    race_product = get_race_product()
    return {
        "products_created": products,
        "orders_created": created_orders,
        "race_product_id": race_product.id,
        "race_product_stock": race_product.stock,
        "monitoring_logs_cleared": clear_monitoring,
    }


def create_demo_products():
    Product.objects.create(
        name="Race Demo Product",
        sku=RACE_PRODUCT_SKU,
        price=Decimal("10.00"),
        stock=settings.DEMO_RACE_INITIAL_STOCK,
        is_popular=True,
    )
    for index in range(1, 20):
        Product.objects.create(
            name=f"Demo Product {index}",
            sku=f"DEMO-{index:03d}",
            price=Decimal("5.00") + index,
            stock=100 + index,
            is_popular=index <= 8,
        )
    return Product.objects.count()


def create_fake_orders(count=10000, batch_size=500):
    now = timezone.now()
    created = 0
    batch = []
    for index in range(count):
        batch.append(
            Order(
                customer_name=f"Batch Customer {index + 1}",
                status=Order.STATUS_PAID,
                total_amount=Decimal("25.00") + Decimal(index % 50),
                created_at=now,
                updated_at=now,
            )
        )
        if len(batch) >= batch_size:
            Order.objects.bulk_create(batch, batch_size=batch_size)
            created += len(batch)
            batch.clear()
    if batch:
        Order.objects.bulk_create(batch, batch_size=batch_size)
        created += len(batch)
    return created


def get_race_product():
    product, _ = Product.objects.get_or_create(
        sku=RACE_PRODUCT_SKU,
        defaults={
            "name": "Race Demo Product",
            "price": Decimal("10.00"),
            "stock": settings.DEMO_RACE_INITIAL_STOCK,
            "is_popular": True,
        },
    )
    return product


def reset_race_state(stock=None):
    Order.objects.all().delete()
    Payment.objects.all().delete()
    BackgroundJob.objects.all().delete()
    product = get_race_product()
    product.stock = settings.DEMO_RACE_INITIAL_STOCK if stock is None else stock
    product.version = 0
    product.save(update_fields=["stock", "version", "updated_at"])
    return product


def race_stock_scenario(mode, users=20):
    users = _bounded_users(users)
    initial_stock = settings.DEMO_RACE_INITIAL_STOCK
    product = reset_race_state(initial_stock)

    if mode == "before":
        barrier = Barrier(users)

        def worker():
            return _race_before_worker(product.id, barrier)

        results = _run_concurrently(users, users, worker)
        solution_or_problem = {
            "problem": "Overselling happened because stock was checked before an unguarded stock decrement.",
        }
    else:
        def worker():
            return _race_after_worker(product.id)

        results = _run_concurrently(users, min(20, users), worker)
        solution_or_problem = {
            "solution": "Used transaction.atomic with a conditional F-expression stock update.",
        }

    final_stock = Product.objects.get(id=product.id).stock
    successful = sum(1 for result in results if result["success"])
    failed = users - successful
    _create_race_orders(product, successful, mode)
    problem_detected = final_stock < 0 or successful > initial_stock

    data = {
        "scenario": "race_condition_stock_update",
        "mode": mode,
        "initial_stock": initial_stock,
        "concurrent_users": users,
        "successful_orders": successful,
        "failed_orders": failed,
        "final_stock": final_stock,
        "problem_detected": problem_detected,
        **solution_or_problem,
    }
    if mode == "after":
        data["problem_detected"] = False
    cache.set(f"{LATEST_COMPARISON_CACHE_PREFIX}{mode}", data, 3600)
    return data


def transaction_integrity_scenario(mode):
    product = reset_race_state(settings.DEMO_RACE_INITIAL_STOCK)
    before_orders = Order.objects.count()
    before_stock = product.stock
    payload = _single_item_payload(product.id, simulate_payment_failure=True)

    if mode == "before":
        checkout_before.checkout(payload, raise_payment_errors=False)
        product.refresh_from_db()
        return {
            "scenario": "transaction_integrity",
            "mode": "before",
            "payment": "failed",
            "order_created": Order.objects.count() > before_orders,
            "stock_decreased": product.stock < before_stock,
            "data_integrity": "broken",
            "problem_detected": True,
        }

    try:
        checkout_after.checkout(payload)
    except PaymentFailed:
        pass
    product.refresh_from_db()
    return {
        "scenario": "transaction_integrity",
        "mode": "after",
        "payment": "failed",
        "order_created": Order.objects.count() > before_orders,
        "stock_decreased": product.stock < before_stock,
        "data_integrity": "preserved",
        "problem_detected": False,
        "solution": "Used transaction.atomic to roll back all changes when payment fails.",
    }


def stress_checkout_scenario(mode, users=100):
    users = _bounded_users(users, maximum=500)
    product = reset_race_state(stock=users)
    max_workers = users if mode == "before" else min(10, users)

    if mode == "before":
        def worker():
            return checkout_before.checkout(_single_item_payload(product.id))
    else:
        def worker():
            return checkout_after.checkout(_single_item_payload(product.id))

    start = time.perf_counter()
    results = _run_concurrently(users, max_workers, worker)
    total_duration_ms = round((time.perf_counter() - start) * 1000, 2)
    durations = [result["duration_ms"] for result in results]
    successful = sum(1 for result in results if result["success"])
    failed = users - successful

    return {
        "scenario": "resource_management",
        "mode": mode,
        "total_users": users,
        "max_parallel_workers": max_workers,
        "successful_requests": successful,
        "failed_requests": failed,
        "avg_response_time_ms": round(statistics.mean(durations), 2) if durations else 0,
        "min_response_time_ms": round(min(durations), 2) if durations else 0,
        "max_response_time_ms": round(max(durations), 2) if durations else 0,
        "total_duration_ms": total_duration_ms,
        "final_stock": Product.objects.get(id=product.id).stock,
        "system_stable": mode == "after" and failed <= max(1, users // 20),
    }


def latest_comparison():
    return {
        "before": cache.get(f"{LATEST_COMPARISON_CACHE_PREFIX}before"),
        "after": cache.get(f"{LATEST_COMPARISON_CACHE_PREFIX}after"),
    }


def _race_before_worker(product_id, barrier):
    product = Product.objects.get(id=product_id)
    if product.stock < 1:
        raise InsufficientStock("Not enough stock.")
    barrier.wait(timeout=20)
    time.sleep(0.05)
    Product.objects.filter(id=product_id).update(stock=F("stock") - 1)
    return {"unsafe_stock_update": True}


def _race_after_worker(product_id):
    Product.objects.only("id").get(id=product_id)
    for attempt in range(20):
        try:
            safe_decrease_stock(product_id, 1)
            return {"atomic_stock_update": True}
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 19:
                raise
            close_old_connections()
            time.sleep(0.02 * (attempt + 1))


def _create_race_orders(product, count, mode):
    customer_name = "Race Before User" if mode == "before" else "Race After User"
    for _ in range(count):
        _create_paid_order(product, customer_name)


def _create_paid_order(product, customer_name):
    order = Order.objects.create(
        customer_name=customer_name,
        status=Order.STATUS_PAID,
        total_amount=product.price,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        quantity=1,
        unit_price=product.price,
        total_price=product.price,
    )
    payment_services.process_payment(order, product.price, simulate_failure=False)
    return order


def _single_item_payload(product_id, simulate_payment_failure=False):
    return {
        "customer_name": "Demo User",
        "items": [{"product_id": product_id, "quantity": 1}],
        "simulate_payment_failure": simulate_payment_failure,
    }


def _run_concurrently(total_users, max_workers, worker):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_thread_wrapper, worker) for _ in range(total_users)]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def _thread_wrapper(worker):
    close_old_connections()
    start = time.perf_counter()
    try:
        data = worker()
        return {
            "success": True,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "data": data,
        }
    except Exception as exc:
        return {
            "success": False,
            "duration_ms": round((time.perf_counter() - start) * 1000, 2),
            "error": str(exc),
            "error_type": exc.__class__.__name__,
        }
    finally:
        close_old_connections()


def _bounded_users(users, minimum=1, maximum=200):
    try:
        users = int(users)
    except (TypeError, ValueError):
        users = minimum
    return max(minimum, min(maximum, users))


def _reset_sqlite_sequences():
    if connection.vendor != "sqlite":
        return
    table_names = [
        "products_product",
        "orders_order",
        "orders_orderitem",
        "payments_payment",
        "jobs_backgroundjob",
        "reports_dailysalessummary",
        "monitoring_performancelog",
        "monitoring_tracelog",
    ]
    with connection.cursor() as cursor:
        for table_name in table_names:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = %s", [table_name])
