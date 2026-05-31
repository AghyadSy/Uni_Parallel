from rest_framework import serializers

from apps.monitoring.models import PerformanceLog, TraceLog


class PerformanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceLog
        fields = [
            "id",
            "request_id",
            "method",
            "path",
            "mode",
            "status_code",
            "duration_ms",
            "db_query_count",
            "user_identifier",
            "created_at",
        ]


class TraceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceLog
        fields = ["id", "request_id", "operation", "step", "message", "metadata", "created_at"]
