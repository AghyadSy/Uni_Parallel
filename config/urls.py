from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/products/", include("apps.products.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/demo/", include("apps.demo.urls")),
    path("api/jobs/", include("apps.jobs.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/monitoring/", include("apps.monitoring.urls")),
]
