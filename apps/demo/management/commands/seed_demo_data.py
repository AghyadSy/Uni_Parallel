from django.core.management.base import BaseCommand

from apps.demo.services import reset_demo_data


class Command(BaseCommand):
    help = "Create products, race-condition stock, and fake paid orders for demos."

    def handle(self, *args, **options):
        result = reset_demo_data(seed_orders=True, clear_monitoring=True)
        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
        for key, value in result.items():
            self.stdout.write(f"{key}: {value}")
