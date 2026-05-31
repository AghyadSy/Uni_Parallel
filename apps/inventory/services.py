from django.db.models import F

from apps.products.models import Product
from core.exceptions import InsufficientStock


def unsafe_decrease_stock(product_id, quantity):
    product = Product.objects.get(id=product_id)
    if product.stock < quantity:
        raise InsufficientStock("Not enough stock.")
    Product.objects.filter(id=product_id).update(stock=F("stock") - quantity)
    return product


def safe_decrease_stock(product_id, quantity):
    # Synchronization point: one conditional SQL update prevents overselling even
    # when many threads try to reserve the final unit at the same time.
    updated = Product.objects.filter(id=product_id, stock__gte=quantity).update(
        stock=F("stock") - quantity,
        version=F("version") + 1,
    )
    if updated != 1:
        raise InsufficientStock("Not enough stock.")
