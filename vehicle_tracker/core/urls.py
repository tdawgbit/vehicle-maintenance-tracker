from django.urls import path

from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("maintenance/", views.maintenance_log_list, name="maintenance_log_list"),
    path("maintenance/add/", views.maintenance_log_create, name="maintenance_log_create"),
    path(
        "maintenance/<int:maintenance_log_id>/edit/",
        views.maintenance_log_update,
        name="maintenance_log_update",
    ),
    path(
        "maintenance/<int:maintenance_log_id>/delete/",
        views.maintenance_log_delete,
        name="maintenance_log_delete",
    ),
    path("vehicles/", views.vehicle_list, name="vehicle_list"),
    path("vehicles/add/", views.vehicle_create, name="vehicle_create"),
    path("vehicles/<int:vehicle_id>/edit/", views.vehicle_update, name="vehicle_update"),
    path("vehicles/<int:vehicle_id>/delete/", views.vehicle_delete, name="vehicle_delete"),
    path("service-types/", views.service_type_list, name="service_type_list"),
    path("service-types/add/", views.service_type_create, name="service_type_create"),
    path(
        "service-types/<int:service_type_id>/edit/",
        views.service_type_update,
        name="service_type_update",
    ),
    path(
        "service-types/<int:service_type_id>/delete/",
        views.service_type_delete,
        name="service_type_delete",
    ),
]
