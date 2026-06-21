import json

from django.core.cache import cache
from django.test import Client, TransactionTestCase, override_settings

from apps.demo import services as demo_services
from apps.jobs.models import BackgroundJob
from apps.monitoring.models import PerformanceLog
from apps.reports.models import DailySalesSummary


@override_settings(
    ALLOW_UNSAFE_DEMO_MODE=True,
    DEMO_INVOICE_DELAY_SECONDS=0.01,
    DEMO_BACKGROUND_JOB_DELAY_SECONDS=0.01,
)
class DemoScenarioTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        cache.clear()
        demo_services.reset_demo_data(seed_orders=False, clear_monitoring=True)
        self.client = Client()

    def test_race_condition_before_allows_overselling(self):
        response = self.client.post("/api/demo/race-stock/?mode=before&users=20", data={})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertTrue(data["problem_detected"])
        self.assertGreater(data["successful_orders"], data["initial_stock"])
        self.assertLess(data["final_stock"], 0)

    def test_race_condition_after_prevents_overselling(self):
        response = self.client.post("/api/demo/race-stock/?mode=after&users=20", data={})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertFalse(data["problem_detected"])
        self.assertEqual(data["successful_orders"], 5)
        self.assertEqual(data["failed_orders"], 15)
        self.assertEqual(data["final_stock"], 0)

    def test_pessimistic_lock_demo_returns_timeline(self):
        response = self.client.post("/api/demo/pessimistic-lock/?request_label=Request%201&hold_seconds=0.01", data={})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["scenario"], "pessimistic_lock_demo")
        self.assertEqual(data["request_label"], "Request 1")
        self.assertTrue(data["lock_acquired"])
        self.assertGreaterEqual(data["waited_for_lock_ms"], 0)
        self.assertIn("Request 1 -> waiting for lock", data["timeline"])
        self.assertIn("Request 1 -> lock acquired", data["timeline"])
        self.assertIn("Request 1 -> finished", data["timeline"])

    def test_pessimistic_lock_batch_returns_ordered_events(self):
        response = self.client.post("/api/demo/pessimistic-lock/batch/?requests=3&hold_seconds=0.01", data={})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["scenario"], "pessimistic_lock_batch")
        self.assertEqual(data["total_requests"], 3)
        self.assertEqual(len(data["requests"]), 3)
        self.assertGreaterEqual(len(data["ordered_events"]), 3)
        self.assertTrue(any("lock acquired" in event["message"] for event in data["ordered_events"]))
        self.assertTrue(any(item["request_number"] == 1 for item in data["requests"]))

    def test_transaction_before_leaves_inconsistent_data(self):
        response = self.client.post("/api/demo/transaction-integrity/?mode=before", data={})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertTrue(data["order_created"])
        self.assertTrue(data["stock_decreased"])
        self.assertEqual(data["initial_stock"], 5)
        self.assertEqual(data["final_stock"], 4)
        self.assertEqual(data["data_integrity"], "broken")

    def test_transaction_after_rolls_back_correctly(self):
        response = self.client.post("/api/demo/transaction-integrity/?mode=after", data={})
        self.assertEqual(response.status_code, 402)
        data = response.json()["data"]

        self.assertFalse(data["order_created"])
        self.assertFalse(data["stock_decreased"])
        self.assertEqual(data["initial_stock"], 5)
        self.assertEqual(data["final_stock"], 5)
        self.assertEqual(data["data_integrity"], "preserved")

    def test_popular_products_after_uses_cache(self):
        first = self.client.get("/api/products/popular/?mode=after")
        second = self.client.get("/api/products/popular/?mode=after")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(first.json()["data"]["cache_hit"])
        self.assertTrue(second.json()["data"]["cache_hit"])

    def test_r10_benchmark_returns_aggregated_statistics(self):
        response = self.client.get("/api/demo/r10-benchmark/?mode=before")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        benchmark = payload["benchmark"]

        self.assertTrue(payload["success"])
        self.assertEqual(set(payload.keys()), {"success", "benchmark"})
        self.assertEqual(benchmark["scenario"], "popular_products_benchmark")
        self.assertEqual(benchmark["mode"], "before")
        self.assertEqual(benchmark["target_endpoint"], "/api/products/popular/?mode=before")
        self.assertEqual(benchmark["total_runs"], 20)
        self.assertEqual(benchmark["successful_runs"], 20)
        self.assertEqual(benchmark["failed_runs"], 0)
        self.assertEqual(benchmark["status"], "PASSED")
        self.assertGreaterEqual(benchmark["success_rate_percent"], 100.0)
        self.assertGreater(benchmark["total_execution_time_ms"], 0)
        self.assertGreater(benchmark["average_response_time_ms"], 0)
        self.assertIn("p50_response_time_ms", benchmark)
        self.assertGreaterEqual(benchmark["max_response_time_ms"], benchmark["min_response_time_ms"])
        self.assertGreater(benchmark["database_queries"], 0)
        self.assertGreater(benchmark["average_queries_per_run"], 0)

    def test_r10_benchmark_after_is_more_efficient_than_before(self):
        before_response = self.client.get("/api/demo/r10-benchmark/?mode=before")
        after_response = self.client.get("/api/demo/r10-benchmark/?mode=after")

        self.assertEqual(before_response.status_code, 200)
        self.assertEqual(after_response.status_code, 200)

        before_benchmark = before_response.json()["benchmark"]
        after_benchmark = after_response.json()["benchmark"]

        self.assertLess(after_benchmark["average_queries_per_run"], before_benchmark["average_queries_per_run"])
        self.assertLess(after_benchmark["average_response_time_ms"], before_benchmark["average_response_time_ms"])

    def test_background_job_created_in_after_checkout(self):
        product = demo_services.get_race_product()
        payload = {
            "customer_name": "Job Demo",
            "items": [{"product_id": product.id, "quantity": 1}],
            "simulate_payment_failure": False,
        }
        response = self.client.post(
            "/api/orders/checkout/?mode=after",
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["data"]["job_created"])
        self.assertEqual(BackgroundJob.objects.filter(status=BackgroundJob.STATUS_PENDING).count(), 1)

    def test_batch_processing_creates_daily_sales_summary(self):
        demo_services.create_fake_orders(count=25)
        response = self.client.post("/api/reports/daily-sales/process/?mode=after", data={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["orders_processed"], 25)
        self.assertTrue(DailySalesSummary.objects.filter(processed_in_chunks=True).exists())

    def test_r9_stress_test_returns_summary_and_preserves_data(self):
        response = self.client.post("/api/demo/r9-stress-test/?users=5", data={})

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]

        self.assertEqual(data["scenario"], "r9_concurrent_checkout")
        self.assertEqual(data["total_requests"], 5)
        self.assertEqual(data["successful_requests"], 5)
        self.assertEqual(data["failed_requests"], 0)
        self.assertFalse(data["system_crash"])
        self.assertEqual(data["final_stock"], 0)
        self.assertTrue(data["data_integrity"]["no_lost_orders"])
        self.assertTrue(data["data_integrity"]["no_duplicate_order_rows"])
        self.assertTrue(data["data_integrity"]["no_lost_payments"])
        self.assertTrue(data["data_integrity"]["no_duplicate_payment_rows"])
        self.assertTrue(data["data_integrity"]["stock_consistent"])
        self.assertTrue(data["data_integrity"]["no_failed_or_pending_records"])
        self.assertTrue(data["data_integrity"]["order_items_match_orders"])

    def test_performance_logs_are_created_for_requests(self):
        before = PerformanceLog.objects.count()
        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        self.assertGreater(PerformanceLog.objects.count(), before)
