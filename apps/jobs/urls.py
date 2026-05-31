from django.urls import path

from apps.jobs.views import JobListAPIView, ProcessPendingJobsAPIView


urlpatterns = [
    path("", JobListAPIView.as_view(), name="job-list"),
    path("process-pending/", ProcessPendingJobsAPIView.as_view(), name="process-pending-jobs"),
]
