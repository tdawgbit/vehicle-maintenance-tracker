from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
import shutil

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import LogService, MaintenanceLog, ServiceType, Vehicle, VehicleType


class TestCoreViews(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tony",
            password="testpass123",
        )
        self.other_user = get_user_model().objects.create_user(
            username="casey",
            password="testpass456",
        )

    def login(self):
        self.client.force_login(self.user)

    def create_vehicle(self, *, owner=None, nickname="Daily", vin=None):
        owner = owner or self.user
        vehicle_type = VehicleType.objects.create(name=f"Car {VehicleType.objects.count() + 1}")
        return Vehicle.objects.create(
            owner=owner,
            year=2021,
            make="Toyota",
            model="Corolla",
            nickname=nickname,
            type=vehicle_type,
            current_mileage=25000,
            vin=vin,
        )

    def create_service_type(self, *, owner=None, name="Oil Change"):
        owner = owner or self.user
        return ServiceType.objects.create(owner=owner, name=name)

    def build_uploaded_photo(
        self,
        *,
        filename="garage-hero.jpg",
        image_format="JPEG",
        size=(1400, 1050),
        quality=95,
        color=(48, 90, 120),
    ):
        image = Image.new("RGB", size, color=color)
        output = BytesIO()
        save_kwargs = {"format": image_format}

        if image_format in {"JPEG", "WEBP"}:
            save_kwargs["quality"] = quality

        image.save(output, **save_kwargs)
        return SimpleUploadedFile(
            filename,
            output.getvalue(),
            content_type=f"image/{image_format.lower()}",
        )

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

    def test_healthcheck_returns_ok_without_login(self):
        response = self.client.get(reverse("healthcheck"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")

    def test_signup_page_loads(self):
        response = self.client.get(reverse("signup"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Join RevLog")

    def test_signup_creates_user_and_logs_them_in(self):
        payload = {
            "username": "newuser",
            "password1": "RevLogPass123!",
            "password2": "RevLogPass123!",
        }

        response = self.client.post(reverse("signup"), payload, follow=True)

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(get_user_model().objects.filter(username="newuser").exists())
        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)

    def test_authenticated_user_is_redirected_away_from_signup(self):
        self.login()

        response = self.client.get(reverse("signup"))

        self.assertRedirects(response, reverse("dashboard"))

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
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.current_mileage, 30123)

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

    def test_dashboard_shows_only_the_logged_in_users_data(self):
        self.login()
        own_vehicle = self.create_vehicle(owner=self.user, nickname="Daily")
        own_service_type = self.create_service_type(owner=self.user, name="Oil Change")
        other_vehicle = self.create_vehicle(owner=self.other_user, nickname="Weekend")
        other_service_type = self.create_service_type(
            owner=self.other_user,
            name="Oil Change",
        )

        own_log = MaintenanceLog.objects.create(
            vehicle=own_vehicle,
            log_date=date(2026, 4, 4),
            total_cost=Decimal("75.00"),
        )
        other_log = MaintenanceLog.objects.create(
            vehicle=other_vehicle,
            log_date=date(2026, 4, 5),
            total_cost=Decimal("200.00"),
        )
        LogService.objects.create(log=own_log, service_type=own_service_type)
        LogService.objects.create(log=other_log, service_type=other_service_type)

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["total_vehicles"], 1)
        self.assertEqual(response.context["total_logs"], 1)
        self.assertEqual(response.context["total_service_types"], 1)
        self.assertEqual(response.context["total_spent"], Decimal("75.00"))
        self.assertContains(response, "Daily")
        self.assertNotContains(response, "Weekend")

    def test_vehicle_list_hides_other_users_vehicles(self):
        self.login()
        own_vehicle = self.create_vehicle(owner=self.user, nickname="Daily")
        other_vehicle = self.create_vehicle(owner=self.other_user, nickname="Weekend")

        response = self.client.get(reverse("vehicle_list"))

        self.assertContains(response, own_vehicle.nickname)
        self.assertNotContains(response, other_vehicle.nickname)

    def test_service_type_list_hides_other_users_service_types(self):
        self.login()
        own_service_type = self.create_service_type(owner=self.user, name="Oil Change")
        other_service_type = self.create_service_type(
            owner=self.other_user,
            name="Suspension",
        )

        response = self.client.get(reverse("service_type_list"))

        self.assertContains(response, own_service_type.name)
        self.assertNotContains(response, other_service_type.name)

    def test_maintenance_log_create_does_not_lower_vehicle_current_mileage(self):
        self.login()
        vehicle = self.create_vehicle()
        oil_change = self.create_service_type(name="Oil Change")

        payload = {
            "vehicle": str(vehicle.pk),
            "log_date": "2026-04-10",
            "mileage_at_service": "24000",
            "shop_name": "Garage",
            "total_cost": "55.00",
            "notes": "",
        }
        payload.update(
            self.build_formset_payload(
                [
                    {
                        "service_type": str(oil_change.pk),
                        "notes": "",
                    },
                ]
            )
        )

        response = self.client.post(reverse("maintenance_log_create"), payload)

        self.assertRedirects(response, reverse("maintenance_log_list"))
        vehicle.refresh_from_db()
        self.assertEqual(vehicle.current_mileage, 25000)

    def test_vehicle_create_saves_uploaded_photo(self):
        self.login()
        vehicle_type = VehicleType.objects.create(name="SUV")
        photo = self.build_uploaded_photo(filename="garage-hero.jpg")

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

    def test_vehicle_create_page_restores_default_vehicle_types_when_missing(self):
        self.login()
        VehicleType.objects.all().delete()

        response = self.client.get(reverse("vehicle_create"))

        self.assertEqual(response.status_code, 200)
        self.assertQuerySetEqual(
            VehicleType.objects.order_by("name").values_list("name", flat=True),
            ["Car", "Motorcycle", "Truck"],
            transform=lambda value: value,
        )
        self.assertContains(response, '<option value="', count=4)

    def test_vehicle_create_resizes_large_photo_dimensions(self):
        self.login()
        vehicle_type = VehicleType.objects.create(name="Coupe")
        photo = self.build_uploaded_photo(
            filename="track-day.jpg",
            size=(4200, 2800),
        )

        payload = {
            "year": "2023",
            "make": "Porsche",
            "model": "911",
            "nickname": "Track Day",
            "type": str(vehicle_type.pk),
            "color": "Silver",
            "current_mileage": "6789",
            "vin": "WP0ZZZ99ZPS123456",
            "notes": "Fresh detail.",
            "photo": photo,
        }

        media_root = Path(__file__).resolve().parent / "test_media_uploads"
        (media_root / "vehicle_photos").mkdir(parents=True, exist_ok=True)

        try:
            with self.settings(MEDIA_ROOT=media_root):
                response = self.client.post(reverse("vehicle_create"), payload)

                self.assertRedirects(response, reverse("vehicle_list"))

                vehicle = Vehicle.objects.get()
                with Image.open(vehicle.photo.path) as saved_photo:
                    self.assertLessEqual(saved_photo.width, 2400)
                    self.assertLessEqual(saved_photo.height, 2400)
        finally:
            shutil.rmtree(media_root, ignore_errors=True)

    def test_vehicle_create_rejects_photo_over_20_mb(self):
        self.login()
        vehicle_type = VehicleType.objects.create(name="Truck")
        photo = SimpleUploadedFile(
            "huge-photo.jpg",
            b"x" * (20 * 1024 * 1024 + 1),
            content_type="image/jpeg",
        )

        payload = {
            "year": "2024",
            "make": "Ford",
            "model": "F-150",
            "nickname": "Big Rig",
            "type": str(vehicle_type.pk),
            "color": "Blue",
            "current_mileage": "5400",
            "vin": "1FTFW1E50RFA12345",
            "notes": "",
            "photo": photo,
        }

        response = self.client.post(reverse("vehicle_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Photo must be 20 MB or smaller.")
        self.assertEqual(Vehicle.objects.count(), 0)

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

    def test_duplicate_service_type_names_are_allowed_for_different_users(self):
        self.create_service_type(owner=self.user, name="Brake Service")
        self.create_service_type(owner=self.other_user, name="Brake Service")

        self.assertEqual(
            ServiceType.objects.filter(name="Brake Service").count(),
            2,
        )

    def test_vehicle_update_returns_404_for_other_users_vehicle(self):
        self.login()
        other_vehicle = self.create_vehicle(owner=self.other_user, nickname="Weekend")

        response = self.client.get(reverse("vehicle_update", args=[other_vehicle.pk]))

        self.assertEqual(response.status_code, 404)

    def test_service_type_update_returns_404_for_other_users_service_type(self):
        self.login()
        other_service_type = self.create_service_type(
            owner=self.other_user,
            name="Brake Service",
        )

        response = self.client.get(
            reverse("service_type_update", args=[other_service_type.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_maintenance_log_delete_returns_404_for_other_users_log(self):
        self.login()
        other_vehicle = self.create_vehicle(owner=self.other_user, nickname="Weekend")
        other_service_type = self.create_service_type(
            owner=self.other_user,
            name="Brake Service",
        )
        other_log = MaintenanceLog.objects.create(
            vehicle=other_vehicle,
            log_date=date(2026, 4, 8),
            total_cost=Decimal("99.00"),
        )
        LogService.objects.create(log=other_log, service_type=other_service_type)

        response = self.client.get(
            reverse("maintenance_log_delete", args=[other_log.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_maintenance_log_create_rejects_other_users_service_type(self):
        self.login()
        vehicle = self.create_vehicle(owner=self.user)
        self.create_service_type(owner=self.user, name="Oil Change")
        other_service_type = self.create_service_type(
            owner=self.other_user,
            name="Suspension",
        )

        payload = {
            "vehicle": str(vehicle.pk),
            "log_date": "2026-04-22",
            "mileage_at_service": "30200",
            "shop_name": "Garage",
            "total_cost": "89.00",
            "notes": "",
        }
        payload.update(
            self.build_formset_payload(
                [
                    {
                        "service_type": str(other_service_type.pk),
                        "notes": "",
                    },
                ]
            )
        )

        response = self.client.post(reverse("maintenance_log_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertEqual(MaintenanceLog.objects.count(), 0)


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
