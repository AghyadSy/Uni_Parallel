import time

from django.core.management.base import BaseCommand

from apps.jobs.services import process_pending_jobs


class Command(BaseCommand):
    help = "Process pending background jobs without an external message broker."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one batch and exit.")
        parser.add_argument("--sleep", type=float, default=2.0, help="Seconds to sleep between batches.")

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Background worker started. Press Ctrl+C to stop."))
        while True:
            summary = process_pending_jobs()
            self.stdout.write(
                f"claimed={summary['claimed']} processed={summary['processed']} failed={summary['failed']}"
            )
            if options["once"]:
                return
            time.sleep(options["sleep"])
