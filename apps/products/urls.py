from django.urls import path

from apps.products.views import PopularProductsAPIView, ProductListCreateAPIView


urlpatterns = [
    path("", ProductListCreateAPIView.as_view(), name="product-list-create"),
    path("popular/", PopularProductsAPIView.as_view(), name="popular-products"),
]
