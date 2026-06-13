from django.urls import path

from apps.demo.views import (
    LatestComparisonAPIView,
    PessimisticLockBatchAPIView,
    PessimisticLockDemoAPIView,
    RaceStockAPIView,
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
    path("comparison/latest/", LatestComparisonAPIView.as_view(), name="demo-latest-comparison"),
]
