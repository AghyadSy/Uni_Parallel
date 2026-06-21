from django.urls import path

from apps.demo.views import (
    LatestComparisonAPIView,
    PessimisticLockBatchAPIView,
    PessimisticLockDemoAPIView,
    PopularProductsBenchmarkAPIView,
    RaceStockAPIView,
    R9StressTestAPIView,
    ResetDataAPIView,
    StressCheckoutAPIView,
    TransactionIntegrityAPIView,
)


urlpatterns = [
    path("reset-data/", ResetDataAPIView.as_view(), name="demo-reset-data"),
    path("race-stock/", RaceStockAPIView.as_view(), name="demo-race-stock"),
    path("pessimistic-lock/batch/", PessimisticLockBatchAPIView.as_view(), name="demo-pessimistic-lock-batch"),
    path("pessimistic-lock/", PessimisticLockDemoAPIView.as_view(), name="demo-pessimistic-lock"),
    path("transaction-integrity/", TransactionIntegrityAPIView.as_view(), name="demo-transaction-integrity"),
    path("stress-checkout/", StressCheckoutAPIView.as_view(), name="demo-stress-checkout"),
    path("r9-stress-test/", R9StressTestAPIView.as_view(), name="demo-r9-stress-test"),
    path("comparison/latest/", LatestComparisonAPIView.as_view(), name="demo-latest-comparison"),
    path("r10-benchmark/", PopularProductsBenchmarkAPIView.as_view(), name="demo-r10-benchmark"),
]
