from rest_framework.views import APIView

from apps.jobs.models import BackgroundJob
from apps.jobs.serializers import BackgroundJobSerializer
from apps.jobs.services import process_pending_jobs
from core.responses import api_success


class JobListAPIView(APIView):
    def get(self, request):
        jobs = BackgroundJob.objects.all()[:100]
        serializer = BackgroundJobSerializer(jobs, many=True)
        return api_success("Jobs loaded.", serializer.data, request=request)


class ProcessPendingJobsAPIView(APIView):
    def post(self, request):
        data = process_pending_jobs()
        return api_success("Pending jobs processed.", data, request=request)
