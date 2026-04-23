from django.core.management.base import BaseCommand

from core.models import VehicleType


DEFAULT_VEHICLE_TYPES = ("Car", "Motorcycle", "Truck")


class Command(BaseCommand):
    help = "Seed default lookup data for local development and demos."

    def handle(self, *args, **options):
        created_names = []

        for name in DEFAULT_VEHICLE_TYPES:
            _, created = VehicleType.objects.get_or_create(name=name)
            if created:
                created_names.append(name)

        if created_names:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created vehicle types: {', '.join(created_names)}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING("Default vehicle types already exist.")
            )
