import time

from django.core.cache import cache
from django.db import connection

from apps.products.models import Product


POPULAR_PRODUCTS_CACHE_KEY = "products:popular:v1"
POPULAR_PRODUCTS_CACHE_TTL = 60


def serialize_product(product):
    return {
        "id": product.id,
        "name": product.name,
        "sku": product.sku,
        "price": str(product.price),
        "stock": product.stock,
        "is_popular": product.is_popular,
    }


def get_popular_products_before():
    start_queries = len(connection.queries)
    start = time.perf_counter()

    products = []
    ids = list(Product.objects.filter(is_popular=True).values_list("id", flat=True))
    for product_id in ids:
        product = Product.objects.get(id=product_id)
        Product.objects.filter(is_popular=True).count()
        time.sleep(0.01)
        products.append(serialize_product(product))

    return {
        "products": products,
        "cache_hit": False,
        "db_query_count": max(0, len(connection.queries) - start_queries),
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        "strategy": "repeated_db_queries",
    }


def get_popular_products_after():
    start_queries = len(connection.queries)
    start = time.perf_counter()
    cached = cache.get(POPULAR_PRODUCTS_CACHE_KEY)

    if cached is not None:
        products = cached
        cache_hit = True
    else:
        queryset = Product.objects.filter(is_popular=True).order_by("id")
        products = [serialize_product(product) for product in queryset]
        cache.set(POPULAR_PRODUCTS_CACHE_KEY, products, POPULAR_PRODUCTS_CACHE_TTL)
        cache_hit = False

    return {
        "products": products,
        "cache_hit": cache_hit,
        "db_query_count": max(0, len(connection.queries) - start_queries),
        "duration_ms": round((time.perf_counter() - start) * 1000, 2),
        "strategy": "django_cache_60_seconds",
    }
