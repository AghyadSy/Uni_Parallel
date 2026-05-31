from django.urls import path

from apps.monitoring.views import MonitoringSummaryAPIView, PerformanceLogListAPIView, TraceLogListAPIView


urlpatterns = [
    path("performance-logs/", PerformanceLogListAPIView.as_view(), name="performance-logs"),
    path("traces/", TraceLogListAPIView.as_view(), name="trace-logs"),
    path("summary/", MonitoringSummaryAPIView.as_view(), name="monitoring-summary"),
]
