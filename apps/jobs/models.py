from django.db import models


class BackgroundJob(models.Model):
    TYPE_GENERATE_INVOICE = "generate_invoice"
    TYPE_SEND_NOTIFICATION = "send_notification"
    TYPE_DAILY_SALES = "daily_sales"

    TYPE_CHOICES = [
        (TYPE_GENERATE_INVOICE, "Generate invoice"),
        (TYPE_SEND_NOTIFICATION, "Send notification"),
        (TYPE_DAILY_SALES, "Daily sales"),
    ]

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_PROCESSED = "processed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_PROCESSED, "Processed"),
        (STATUS_FAILED, "Failed"),
    ]

    type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payload = models.JSONField(default=dict)
    result = models.JSONField(null=True, blank=True)
    error = models.TextField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.type} - {self.status}"
