from rest_framework.views import APIView

from apps.demo import services
from core.aop.tracing import trace_operation
from core.responses import api_success


class ResetDataAPIView(APIView):
    def post(self, request):
        seed_orders = request.GET.get("seed_orders", "false").lower() == "true"
        data = services.reset_demo_data(seed_orders=seed_orders)
        return api_success("Demo data reset.", data, request=request)


class RaceStockAPIView(APIView):
    @trace_operation("race_stock")
    def post(self, request):
        users = request.GET.get("users", 20)
        data = services.race_stock_scenario(request.demo_mode, users=users)
        return api_success("Race stock scenario completed.", data, request=request)


class TransactionIntegrityAPIView(APIView):
    @trace_operation("transaction_integrity")
    def post(self, request):
        data = services.transaction_integrity_scenario(request.demo_mode)
        return api_success("Transaction integrity scenario completed.", data, request=request)


class StressCheckoutAPIView(APIView):
    @trace_operation("stress_checkout")
    def post(self, request):
        users = request.GET.get("users", 100)
        data = services.stress_checkout_scenario(request.demo_mode, users=users)
        return api_success("Stress checkout scenario completed.", data, request=request)


class PessimisticLockDemoAPIView(APIView):
    @trace_operation("pessimistic_lock_demo")
    def post(self, request):
        request_label = request.GET.get("request_label")
        hold_seconds = request.GET.get("hold_seconds", 5)
        data = services.pessimistic_lock_demo(request_label=request_label, hold_seconds=hold_seconds)
        return api_success("Pessimistic lock demo completed.", data, request=request)


class PessimisticLockBatchAPIView(APIView):
    @trace_operation("pessimistic_lock_batch")
    def post(self, request):
        total_requests = request.GET.get("requests", 10)
        hold_seconds = request.GET.get("hold_seconds", 5)
        data = services.pessimistic_lock_batch(total_requests=total_requests, hold_seconds=hold_seconds)
        return api_success("Pessimistic lock batch completed.", data, request=request)


class LatestComparisonAPIView(APIView):
    def get(self, request):
        data = services.latest_comparison()
        return api_success("Latest comparison loaded.", data, request=request)
