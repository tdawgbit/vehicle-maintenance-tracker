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
        "year",
        "make",
        "model",
        "nickname",
        "type",
        "has_photo",
        "current_mileage",
        "vin",
    )
    list_filter = ("type", "make", "year")
    search_fields = ("make", "model", "nickname", "vin")

    @admin.display(boolean=True, description="Photo")
    def has_photo(self, obj):
        return bool(obj.photo)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "default_interval_miles", "default_interval_days")
    search_fields = ("name",)


class LogServiceInline(admin.TabularInline):
    model = LogService
    extra = 1


@admin.register(MaintenanceLog)
class MaintenanceLogAdmin(admin.ModelAdmin):
    list_display = ("id", "vehicle", "log_date", "mileage_at_service", "shop_name", "total_cost")
    list_filter = ("log_date", "vehicle__make")
    search_fields = ("vehicle__make", "vehicle__model", "shop_name", "notes")
    inlines = [LogServiceInline]


@admin.register(LogService)
class LogServiceAdmin(admin.ModelAdmin):
    list_display = ("id", "log", "service_type", "cost")
    list_filter = ("service_type",)
    search_fields = ("service_type__name", "notes")
