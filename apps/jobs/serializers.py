from rest_framework import serializers

from apps.jobs.models import BackgroundJob


class BackgroundJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackgroundJob
        fields = [
            "id",
            "type",
            "status",
            "payload",
            "result",
            "error",
            "attempts",
            "created_at",
            "updated_at",
            "processed_at",
        ]
