from django.urls import path

from apps.demo.views import (
    LatestComparisonAPIView,
    RaceStockAPIView,
    ResetDataAPIView,
    StressCheckoutAPIView,
    TransactionIntegrityAPIView,
)


urlpatterns = [
    path("reset-data/", ResetDataAPIView.as_view(), name="demo-reset-data"),
    path("race-stock/", RaceStockAPIView.as_view(), name="demo-race-stock"),
    path("transaction-integrity/", TransactionIntegrityAPIView.as_view(), name="demo-transaction-integrity"),
    path("stress-checkout/", StressCheckoutAPIView.as_view(), name="demo-stress-checkout"),
    path("comparison/latest/", LatestComparisonAPIView.as_view(), name="demo-latest-comparison"),
]
