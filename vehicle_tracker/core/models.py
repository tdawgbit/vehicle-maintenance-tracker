from django.db import models


class VehicleType(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "vehicle_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vehicle(models.Model):
    year = models.IntegerField()
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    nickname = models.CharField(max_length=100, blank=True, null=True)
    type = models.ForeignKey(
        VehicleType,
        on_delete=models.PROTECT,
        db_column="type_id",
        related_name="vehicles",
    )
    color = models.CharField(max_length=50, blank=True, null=True)
    current_mileage = models.IntegerField(blank=True, null=True)
    vin = models.CharField(max_length=50, unique=True, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "vehicles"
        ordering = ["-year", "make", "model"]

    def __str__(self):
        base = f"{self.year} {self.make} {self.model}"
        return f'{base} - "{self.nickname}"' if self.nickname else base


class ServiceType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    default_interval_miles = models.IntegerField(blank=True, null=True)
    default_interval_days = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "service_types"
        ordering = ["name"]

    def __str__(self):
        return self.name


class MaintenanceLog(models.Model):
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        db_column="vehicle_id",
        related_name="maintenance_logs",
    )
    log_date = models.DateField()
    mileage_at_service = models.IntegerField(blank=True, null=True)
    shop_name = models.CharField(max_length=200, blank=True, null=True)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    service_types = models.ManyToManyField(
        ServiceType,
        through="LogService",
        related_name="maintenance_logs",
        through_fields=("log", "service_type"),
    )

    class Meta:
        db_table = "maintenance_logs"
        ordering = ["-log_date", "-id"]

    def __str__(self):
        return f"{self.vehicle} - {self.log_date}"


class LogService(models.Model):
    log = models.ForeignKey(
        MaintenanceLog,
        on_delete=models.CASCADE,
        db_column="log_id",
        related_name="log_services",
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        db_column="service_type_id",
        related_name="log_services",
    )
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    notes = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "log_services"
        unique_together = ("log", "service_type")

    def __str__(self):
        return f"{self.log} - {self.service_type}"
