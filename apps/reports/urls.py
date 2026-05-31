from django.urls import path

from apps.reports.views import DailySalesProcessAPIView


urlpatterns = [
    path("daily-sales/process/", DailySalesProcessAPIView.as_view(), name="daily-sales-process"),
]
