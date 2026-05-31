from django.contrib import admin

from apps.jobs.models import BackgroundJob


@admin.register(BackgroundJob)
class BackgroundJobAdmin(admin.ModelAdmin):
    list_display = ("id", "type", "status", "attempts", "created_at", "processed_at")
    list_filter = ("type", "status")
