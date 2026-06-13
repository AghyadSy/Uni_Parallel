from django.db import transaction
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
    # Lock the product row so concurrent transactions across instances serialize
    # stock changes through the database before decrementing inventory.
    with transaction.atomic():
        product = Product.objects.select_for_update().get(id=product_id)
        if product.stock < quantity:
            raise InsufficientStock("Not enough stock.")

        Product.objects.filter(id=product_id).update(
            stock=F("stock") - quantity,
            version=F("version") + 1,
        )
