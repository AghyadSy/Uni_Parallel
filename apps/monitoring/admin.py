from django.contrib import admin

from apps.monitoring.models import PerformanceLog, TraceLog


@admin.register(PerformanceLog)
class PerformanceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "method", "path", "mode", "status_code", "duration_ms", "db_query_count", "created_at")
    list_filter = ("mode", "status_code")
    search_fields = ("request_id", "path")


@admin.register(TraceLog)
class TraceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "operation", "step", "request_id", "created_at")
    list_filter = ("operation", "step")
