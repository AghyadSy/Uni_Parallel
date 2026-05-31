import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import BackgroundJob


def process_pending_jobs(limit=10):
    processed = 0
    failed = 0
    results = []
    job_ids = list(
        BackgroundJob.objects.filter(status=BackgroundJob.STATUS_PENDING)
        .order_by("created_at")
        .values_list("id", flat=True)[:limit]
    )

    for job_id in job_ids:
        job = _claim_job(job_id)
        if job is None:
            continue
        try:
            result = _process_job(job)
            job.status = BackgroundJob.STATUS_PROCESSED
            job.result = result
            job.error = None
            job.processed_at = timezone.now()
            job.save(update_fields=["status", "result", "error", "processed_at", "updated_at"])
            processed += 1
            results.append({"job_id": job.id, "status": job.status, "result": result})
        except Exception as exc:
            job.status = BackgroundJob.STATUS_FAILED
            job.error = str(exc)
            job.processed_at = timezone.now()
            job.save(update_fields=["status", "error", "processed_at", "updated_at"])
            failed += 1
            results.append({"job_id": job.id, "status": job.status, "error": str(exc)})

    return {
        "claimed": len(job_ids),
        "processed": processed,
        "failed": failed,
        "results": results,
    }


def _claim_job(job_id):
    with transaction.atomic():
        job = BackgroundJob.objects.select_for_update().get(id=job_id)
        if job.status != BackgroundJob.STATUS_PENDING:
            return None
        job.status = BackgroundJob.STATUS_PROCESSING
        job.attempts += 1
        job.save(update_fields=["status", "attempts", "updated_at"])
        return job


def _process_job(job):
    if job.type == BackgroundJob.TYPE_GENERATE_INVOICE:
        time.sleep(settings.DEMO_BACKGROUND_JOB_DELAY_SECONDS)
        return {
            "invoice_id": f"INV-{job.payload.get('order_id')}",
            "order_id": job.payload.get("order_id"),
            "message": "Invoice generated in background worker.",
        }
    if job.type == BackgroundJob.TYPE_SEND_NOTIFICATION:
        time.sleep(0.05)
        return {"message": "Notification sent."}
    if job.type == BackgroundJob.TYPE_DAILY_SALES:
        return {"message": "Daily sales job delegated to reports service."}
    raise ValueError(f"Unsupported job type: {job.type}")
