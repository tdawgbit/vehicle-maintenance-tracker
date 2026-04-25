from django.contrib import admin
from .models import VehicleType, Vehicle, ServiceType, MaintenanceLog, LogService


@admin.register(VehicleType)
class VehicleTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "owner",
        "year",
        "make",
        "model",
        "nickname",
        "type",
        "has_photo",
        "current_mileage",
        "vin",
    )
    list_filter = ("owner", "type", "make", "year")
    search_fields = ("owner__username", "make", "model", "nickname", "vin")

    @admin.display(boolean=True, description="Photo")
    def has_photo(self, obj):
        return bool(obj.photo)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "name", "default_interval_miles", "default_interval_days")
    list_filter = ("owner",)
    search_fields = ("owner__username", "name")


class LogServiceInline(admin.TabularInline):
    model = LogService
    extra = 1


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "vehicle_owner", "log_date", "mileage_at_service", "shop_name", "total_cost")
    list_filter = ("log_date", "vehicle__owner", "vehicle__make")
    search_fields = ("vehicle__owner__username", "vehicle__make", "vehicle__model", "shop_name", "notes")
    inlines = [LogServiceInline]

    @admin.display(ordering="vehicle__owner", description="Owner")
    def vehicle_owner(self, obj):
        return obj.vehicle.owner


@admin.register(LogService)
class LogServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "log", "service_type", "cost")
    list_filter = ("service_type",)
    search_fields = ("service_type__name", "notes")
