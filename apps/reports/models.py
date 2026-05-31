from django.db import models


class DailySalesSummary(models.Model):
    date = models.DateField()
    total_orders = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    processed_in_chunks = models.BooleanField(default=False)
    chunk_size = models.PositiveIntegerField(default=0)
    duration_ms = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.date} - {self.total_orders} orders"
