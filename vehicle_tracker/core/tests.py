from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path
import shutil

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import LogService, MaintenanceLog, ServiceType, Vehicle, VehicleType


class TestCoreViews(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tony",
            password="testpass123",
        )

    def login(self):
        self.client.force_login(self.user)

    def create_vehicle(self, *, nickname="Daily"):
        vehicle_type = VehicleType.objects.create(name=f"Car {VehicleType.objects.count() + 1}")
        return Vehicle.objects.create(
            year=2021,
            make="Toyota",
            model="Corolla",
            nickname=nickname,
            type=vehicle_type,
            current_mileage=25000,
        )

    def create_service_type(self, *, name="Oil Change"):
        return ServiceType.objects.create(name=name)

    def build_formset_payload(self, rows):
        payload = {
            "services-TOTAL_FORMS": str(len(rows)),
            "services-INITIAL_FORMS": "0",
            "services-MIN_NUM_FORMS": "0",
            "services-MAX_NUM_FORMS": "1000",
        }

        for index, row in enumerate(rows):
            payload[f"services-{index}-service_type"] = row.get("service_type", "")
            payload[f"services-{index}-notes"] = row.get("notes", "")

        return payload

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('dashboard')}",
        )

    def test_maintenance_log_create_redirects_until_dependencies_exist(self):
        self.login()

        response = self.client.get(reverse("maintenance_log_create"), follow=True)

        self.assertRedirects(response, reverse("vehicle_create"))
        self.assertContains(response, "Add a vehicle before creating a maintenance log.")

        self.create_vehicle()
        response = self.client.get(reverse("maintenance_log_create"), follow=True)

        self.assertRedirects(response, reverse("service_type_create"))
        self.assertContains(response, "Add a service type before creating a maintenance log.")

    def test_maintenance_log_create_saves_log_and_services(self):
        self.login()
        vehicle = self.create_vehicle()
        oil_change = self.create_service_type(name="Oil Change")
        tire_rotation = self.create_service_type(name="Tire Rotation")

        payload = {
            "vehicle": str(vehicle.pk),
            "log_date": "2026-04-20",
            "mileage_at_service": "30123",
            "shop_name": "  Corner Garage  ",
            "total_cost": "149.99",
            "notes": "  Changed oil and rotated tires.  ",
        }
        payload.update(
            self.build_formset_payload(
                [
                    {
                        "service_type": str(oil_change.pk),
                        "notes": "  Synthetic oil  ",
                    },
                    {
                        "service_type": str(tire_rotation.pk),
                        "notes": "  Front to back  ",
                    },
                ]
            )
        )

        response = self.client.post(reverse("maintenance_log_create"), payload)

        self.assertRedirects(response, reverse("maintenance_log_list"))
        self.assertEqual(MaintenanceLog.objects.count(), 1)

        maintenance_log = MaintenanceLog.objects.get()
        self.assertEqual(maintenance_log.vehicle, vehicle)
        self.assertEqual(maintenance_log.shop_name, "Corner Garage")
        self.assertEqual(maintenance_log.notes, "Changed oil and rotated tires.")
        self.assertEqual(maintenance_log.total_cost, Decimal("149.99"))

        log_services = list(
            maintenance_log.log_services.order_by("service_type__name").values_list(
                "service_type__name",
                "notes",
            )
        )
        self.assertEqual(
            log_services,
            [
                ("Oil Change", "Synthetic oil"),
                ("Tire Rotation", "Front to back"),
            ],
        )

    def test_maintenance_log_create_rejects_duplicate_service_types(self):
        self.login()
        vehicle = self.create_vehicle()
        oil_change = self.create_service_type(name="Oil Change")

        payload = {
            "vehicle": str(vehicle.pk),
            "log_date": "2026-04-20",
            "mileage_at_service": "30123",
            "shop_name": "Garage",
            "total_cost": "120.00",
            "notes": "",
        }
        payload.update(
            self.build_formset_payload(
                [
                    {
                        "service_type": str(oil_change.pk),
                        "notes": "",
                    },
                    {
                        "service_type": str(oil_change.pk),
                        "notes": "",
                    },
                ]
            )
        )

        response = self.client.post(reverse("maintenance_log_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please correct the duplicate data for service_type.")
        self.assertEqual(MaintenanceLog.objects.count(), 0)

    def test_maintenance_history_filters_by_vehicle(self):
        self.login()
        service_type = self.create_service_type(name="Oil Change")
        first_vehicle = self.create_vehicle(nickname="Daily")
        second_vehicle = self.create_vehicle(nickname="Weekend")

        first_log = MaintenanceLog.objects.create(
            vehicle=first_vehicle,
            log_date=date(2026, 4, 1),
            total_cost=Decimal("50.00"),
        )
        second_log = MaintenanceLog.objects.create(
            vehicle=second_vehicle,
            log_date=date(2026, 4, 2),
            total_cost=Decimal("80.00"),
        )
        LogService.objects.create(log=first_log, service_type=service_type)
        LogService.objects.create(log=second_log, service_type=service_type)

        response = self.client.get(
            reverse("maintenance_log_list"),
            {"vehicle": second_vehicle.pk},
        )

        self.assertContains(response, reverse("maintenance_log_update", args=[second_log.pk]))
        self.assertNotContains(response, reverse("maintenance_log_update", args=[first_log.pk]))

    def test_vehicle_create_saves_uploaded_photo(self):
        self.login()
        vehicle_type = VehicleType.objects.create(name="SUV")
        photo = SimpleUploadedFile(
            "garage-hero.jpg",
            b"fake-image-content",
            content_type="image/jpeg",
        )

        payload = {
            "year": "2022",
            "make": "Ford",
            "model": "Bronco",
            "nickname": " Trail Rig ",
            "type": str(vehicle_type.pk),
            "color": "Green",
            "current_mileage": "12345",
            "vin": "1FMDE5CH9NLA12345",
            "notes": "  Ready for road trips.  ",
            "photo": photo,
        }

        media_root = Path(__file__).resolve().parent / "test_media_uploads"
        (media_root / "vehicle_photos").mkdir(parents=True, exist_ok=True)

        try:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(reverse("vehicle_create"), payload)

                self.assertRedirects(response, reverse("vehicle_list"))

                vehicle = Vehicle.objects.get()
                self.assertEqual(vehicle.nickname, "Trail Rig")
                self.assertTrue(vehicle.photo.name.startswith("vehicle_photos/"))
                self.assertTrue(Path(vehicle.photo.path).exists())
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    def test_service_type_delete_is_blocked_when_in_use(self):
        self.login()
        vehicle = self.create_vehicle()
        service_type = self.create_service_type(name="Brake Service")
        maintenance_log = MaintenanceLog.objects.create(
            vehicle=vehicle,
            log_date=date.today() - timedelta(days=7),
            total_cost=Decimal("300.00"),
        )
        LogService.objects.create(log=maintenance_log, service_type=service_type)

        response = self.client.post(
            reverse("service_type_delete", args=[service_type.pk]),
            follow=True,
        )

        self.assertRedirects(response, reverse("service_type_list"))
        self.assertContains(
            response,
            "This service type cannot be deleted because it is used in maintenance logs.",
        )
        self.assertTrue(ServiceType.objects.filter(pk=service_type.pk).exists())


class TestManagementCommands(TestCase):
    def test_seed_initial_data_creates_default_vehicle_types(self):
        output = StringIO()

        call_command("seed_initial_data", stdout=output)

        self.assertQuerySetEqual(
            VehicleType.objects.order_by("name").values_list("name", flat=True),
            ["Car", "Motorcycle", "Truck"],
            transform=lambda value: value,
        )
        self.assertIn("Created vehicle types", output.getvalue())

    def test_seed_initial_data_is_idempotent(self):
        VehicleType.objects.create(name="Car")
        output = StringIO()

        call_command("seed_initial_data", stdout=output)

        self.assertQuerySetEqual(
            VehicleType.objects.order_by("name").values_list("name", flat=True),
            ["Car", "Motorcycle", "Truck"],
            transform=lambda value: value,
        )
        self.assertIn("Created vehicle types", output.getvalue())
