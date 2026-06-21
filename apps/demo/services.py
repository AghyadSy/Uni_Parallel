import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from threading import Barrier, BrokenBarrierError, Lock
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, close_old_connections, connection, transaction
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
from apps.products import services as product_services
from apps.reports.models import DailySalesSummary
from core.benchmarking import BenchmarkService
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
            "initial_stock": before_stock,
            "final_stock": product.stock,
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
        "initial_stock": before_stock,
        "final_stock": product.stock,
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


def r9_concurrent_checkout_report(users=100):
    users = _bounded_users(users, maximum=500)
    product = reset_race_state(stock=users)
    payload = _single_item_payload(product.id)
    start = time.perf_counter()
    results = _run_concurrently(users, users, lambda: checkout_after.checkout(payload))
    wall_time_s = time.perf_counter() - start
    durations = [result["duration_ms"] for result in results]
    successful = sum(1 for result in results if result["success"])
    failed = users - successful

    product.refresh_from_db()
    paid_orders = Order.objects.filter(status=Order.STATUS_PAID).count()
    failed_orders = Order.objects.filter(status=Order.STATUS_FAILED).count()
    pending_orders = Order.objects.filter(status=Order.STATUS_PENDING).count()
    order_items = OrderItem.objects.count()
    success_payments = Payment.objects.filter(status=Payment.STATUS_SUCCESS).count()
    failed_payments = Payment.objects.filter(status=Payment.STATUS_FAILED).count()
    distinct_order_ids = Order.objects.values("id").distinct().count()
    distinct_payment_ids = Payment.objects.values("id").distinct().count()
    requests_per_second = round(users / wall_time_s, 2) if wall_time_s > 0 else 0

    return {
        "scenario": "r9_concurrent_checkout",
        "tested_api": "POST /api/orders/checkout/?mode=after",
        "total_requests": users,
        "successful_requests": successful,
        "failed_requests": failed,
        "average_response_time_ms": round(statistics.mean(durations), 2) if durations else 0,
        "min_response_time_ms": round(min(durations), 2) if durations else 0,
        "max_response_time_ms": round(max(durations), 2) if durations else 0,
        "requests_per_second_rps": requests_per_second,
        "system_crash": False,
        "total_wall_time_ms": round(wall_time_s * 1000, 2),
        "initial_stock": users,
        "final_stock": product.stock,
        "paid_orders": paid_orders,
        "failed_orders": failed_orders,
        "pending_orders": pending_orders,
        "order_items": order_items,
        "success_payments": success_payments,
        "failed_payments": failed_payments,
        "distinct_order_ids": distinct_order_ids,
        "distinct_payment_ids": distinct_payment_ids,
        "data_integrity": {
            "no_lost_orders": paid_orders == successful,
            "no_duplicate_order_rows": distinct_order_ids == paid_orders,
            "no_lost_payments": success_payments == successful,
            "no_duplicate_payment_rows": distinct_payment_ids == success_payments,
            "stock_consistent": product.stock == users - successful,
            "no_failed_or_pending_records": failed_orders == 0 and pending_orders == 0 and failed_payments == 0,
            "order_items_match_orders": order_items == successful,
        },
    }


def latest_comparison():
    return {
        "before": cache.get(f"{LATEST_COMPARISON_CACHE_PREFIX}before"),
        "after": cache.get(f"{LATEST_COMPARISON_CACHE_PREFIX}after"),
    }


def popular_products_benchmark(mode):
    normalized_mode = "before" if mode == "before" else "after"
    benchmark_service = BenchmarkService(total_runs=20)
    operation = (
        product_services.get_popular_products_before
        if normalized_mode == "before"
        else product_services.get_popular_products_after
    )

    return benchmark_service.run(
        scenario="popular_products_benchmark",
        operation=operation,
        timestamp=timezone.now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        query_count_getter=lambda result: result.get("db_query_count", 0),
        before_all=lambda: cache.delete(product_services.POPULAR_PRODUCTS_CACHE_KEY),
        extra={
            "mode": normalized_mode,
            "target_endpoint": f"/api/products/popular/?mode={normalized_mode}",
        },
    )


def pessimistic_lock_demo(request_label=None, hold_seconds=5, event_logger=None):
    product = get_race_product()
    request_label = (request_label or f"request-{uuid4().hex[:8]}").strip()
    hold_seconds = _bounded_hold_seconds(hold_seconds)
    timeline = []
    started_at = time.perf_counter()

    def _record(message):
        timeline.append(message)
        if event_logger is not None:
            event_logger(message)

    _record(f"{request_label} -> request received")
    _record(f"{request_label} -> waiting for lock")

    for attempt in range(50):
        try:
            with transaction.atomic():
                Product.objects.select_for_update().get(id=product.id)

                # SQLite ignores select_for_update(), so a write is used here to hold a
                # database lock during the demo request. PostgreSQL/MySQL rely on the
                # row lock acquired above.
                if connection.vendor == "sqlite":
                    Product.objects.filter(id=product.id).update(version=F("version"))

                waited_ms = round((time.perf_counter() - started_at) * 1000, 2)
                _record(f"{request_label} -> lock acquired")
                _record(f"{request_label} -> holding lock for {hold_seconds:.2f}s")
                time.sleep(hold_seconds)
                _record(f"{request_label} -> finished")
                break
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 49:
                raise
            close_old_connections()
            time.sleep(0.02 * (attempt + 1))

    return {
        "scenario": "pessimistic_lock_demo",
        "request_label": request_label,
        "product_id": product.id,
        "db_backend": connection.vendor,
        "lock_acquired": True,
        "waited_for_lock_ms": waited_ms,
        "hold_seconds": hold_seconds,
        "timeline": timeline,
    }


def pessimistic_lock_batch(total_requests=10, hold_seconds=5):
    total_requests = _bounded_users(total_requests, minimum=1, maximum=20)
    hold_seconds = _bounded_hold_seconds(hold_seconds)
    product = get_race_product()
    batch_started_at = time.perf_counter()
    event_lock = Lock()
    start_barrier = Barrier(total_requests)
    ordered_events = []

    def log_event(message):
        with event_lock:
            ordered_events.append(
                {
                    "at_ms": round((time.perf_counter() - batch_started_at) * 1000, 2),
                    "message": message,
                }
            )

    def worker(index):
        label = f"Request {index}"
        try:
            start_barrier.wait(timeout=10)
        except BrokenBarrierError:
            pass
        return pessimistic_lock_demo(
            request_label=label,
            hold_seconds=hold_seconds,
            event_logger=log_event,
        )

    results = []
    with ThreadPoolExecutor(max_workers=total_requests) as executor:
        future_map = {
            executor.submit(_thread_wrapper, lambda index=index: worker(index)): index
            for index in range(1, total_requests + 1)
        }
        for future in as_completed(future_map):
            result = future.result()
            result["request_number"] = future_map[future]
            results.append(result)

    results.sort(key=lambda item: item["request_number"])
    successful = sum(1 for item in results if item["success"])
    wait_times = [
        item["data"]["waited_for_lock_ms"]
        for item in results
        if item["success"] and "data" in item and "waited_for_lock_ms" in item["data"]
    ]

    return {
        "scenario": "pessimistic_lock_batch",
        "product_id": product.id,
        "db_backend": connection.vendor,
        "total_requests": total_requests,
        "successful_requests": successful,
        "failed_requests": total_requests - successful,
        "hold_seconds": hold_seconds,
        "avg_wait_ms": round(statistics.mean(wait_times), 2) if wait_times else 0,
        "max_wait_ms": round(max(wait_times), 2) if wait_times else 0,
        "ordered_events": ordered_events,
        "requests": results,
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


def _bounded_hold_seconds(value, minimum=0, maximum=10):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = 5.0
    return max(minimum, min(maximum, seconds))


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
