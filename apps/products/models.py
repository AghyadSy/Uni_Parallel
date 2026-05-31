from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.IntegerField(default=0)
    is_popular = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.sku})"
