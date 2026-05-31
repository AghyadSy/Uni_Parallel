from django.db import models


class PerformanceLog(models.Model):
    request_id = models.CharField(max_length=64, db_index=True)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    mode = models.CharField(max_length=20, default="after")
    status_code = models.PositiveIntegerField()
    duration_ms = models.FloatField()
    db_query_count = models.PositiveIntegerField()
    user_identifier = models.CharField(max_length=120, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.path} {self.duration_ms}ms"


class TraceLog(models.Model):
    request_id = models.CharField(max_length=64, db_index=True, null=True, blank=True)
    operation = models.CharField(max_length=80)
    step = models.CharField(max_length=80)
    message = models.TextField()
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.operation}:{self.step}"
