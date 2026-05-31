from rest_framework.views import APIView

from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from apps.products import services
from core.aop.tracing import trace_operation
from core.responses import api_success


class ProductListCreateAPIView(APIView):
    def get(self, request):
        serializer = ProductSerializer(Product.objects.all(), many=True)
        return api_success("Products loaded.", serializer.data, request=request)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return api_success("Product created.", ProductSerializer(product).data, request=request, status=201)


class PopularProductsAPIView(APIView):
    @trace_operation("popular_products")
    def get(self, request):
        if request.demo_mode == "before":
            data = services.get_popular_products_before()
        else:
            data = services.get_popular_products_after()
        return api_success("Popular products loaded.", data, request=request)
