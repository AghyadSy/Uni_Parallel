from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.orders.serializers import CheckoutRequestSerializer, OrderSerializer
from apps.orders.services import checkout_service
from core.aop.tracing import trace_operation
from core.responses import api_success


class CheckoutAPIView(APIView):
    @trace_operation("checkout")
    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = checkout_service.checkout(serializer.validated_data, request.demo_mode)
        return api_success("Checkout completed.", data, request=request, status=201)


class OrderListAPIView(APIView):
    def get(self, request):
        orders = Order.objects.prefetch_related("items__product").all()[:100]
        serializer = OrderSerializer(orders, many=True)
        return api_success("Orders loaded.", serializer.data, request=request)


class OrderDetailAPIView(APIView):
    def get(self, request, pk):
        order = get_object_or_404(Order.objects.prefetch_related("items__product"), pk=pk)
        serializer = OrderSerializer(order)
        return api_success("Order loaded.", serializer.data, request=request)
