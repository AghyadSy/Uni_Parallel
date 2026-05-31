from django.urls import path

from apps.orders.views import CheckoutAPIView, OrderDetailAPIView, OrderListAPIView


urlpatterns = [
    path("checkout/", CheckoutAPIView.as_view(), name="checkout"),
    path("", OrderListAPIView.as_view(), name="order-list"),
    path("<int:pk>/", OrderDetailAPIView.as_view(), name="order-detail"),
]
