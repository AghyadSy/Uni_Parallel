from django.contrib import admin

from apps.products.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "sku", "price", "stock", "is_popular", "version")
    search_fields = ("name", "sku")
    list_filter = ("is_popular",)
