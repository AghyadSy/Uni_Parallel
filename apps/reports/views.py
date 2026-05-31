from rest_framework.views import APIView

from apps.reports import services
from core.aop.tracing import trace_operation
from core.responses import api_success


class DailySalesProcessAPIView(APIView):
    @trace_operation("daily_sales_report")
    def post(self, request):
        if request.demo_mode == "before":
            data = services.process_daily_sales_before()
        else:
            data = services.process_daily_sales_after()
        return api_success("Daily sales processed.", data, request=request)
