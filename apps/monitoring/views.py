from django.db.models import Avg, Count
from rest_framework.views import APIView

from apps.monitoring.models import PerformanceLog, TraceLog
from apps.monitoring.serializers import PerformanceLogSerializer, TraceLogSerializer
from core.responses import api_success


class PerformanceLogListAPIView(APIView):
    def get(self, request):
        logs = PerformanceLog.objects.all()[:200]
        serializer = PerformanceLogSerializer(logs, many=True)
        return api_success("Performance logs loaded.", serializer.data, request=request)


class TraceLogListAPIView(APIView):
    def get(self, request):
        traces = TraceLog.objects.all()[:200]
        serializer = TraceLogSerializer(traces, many=True)
        return api_success("Trace logs loaded.", serializer.data, request=request)


class MonitoringSummaryAPIView(APIView):
    def get(self, request):
        by_mode = list(
            PerformanceLog.objects.values("mode")
            .annotate(
                request_count=Count("id"),
                avg_duration_ms=Avg("duration_ms"),
                avg_db_queries=Avg("db_query_count"),
            )
            .order_by("mode")
        )
        return api_success(
            "Monitoring summary loaded.",
            {
                "performance_by_mode": by_mode,
                "total_performance_logs": PerformanceLog.objects.count(),
                "total_trace_logs": TraceLog.objects.count(),
            },
            request=request,
        )
