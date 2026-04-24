from datetime import date

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import (
    LogServiceFormSet,
    MaintenanceLogForm,
    SignUpForm,
    ServiceTypeForm,
    VehicleForm,
)
from .models import LogService, MaintenanceLog, ServiceType, Vehicle


def build_vehicle_label(vehicle):
    base = f"{vehicle.year} {vehicle.make} {vehicle.model}"
    return f'{base} - "{vehicle.nickname}"' if vehicle.nickname else base


def build_service_type_label(service_type):
    return service_type.name


def build_log_service_summary(log):
    return ", ".join(
        log_service.service_type.name for log_service in log.log_services.all()
    )


def get_post_auth_redirect(request):
    redirect_to = request.POST.get("next") or request.GET.get("next")
    if redirect_to and url_has_allowed_host_and_scheme(
        redirect_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect_to

    return settings.LOGIN_REDIRECT_URL


def sync_vehicle_current_mileage(vehicle, mileage_at_service):
    if mileage_at_service is None:
        return

    if vehicle.current_mileage is None or mileage_at_service > vehicle.current_mileage:
        vehicle.current_mileage = mileage_at_service
        vehicle.save(update_fields=["current_mileage"])


def get_maintenance_log_queryset():
    return (
        MaintenanceLog.objects.select_related("vehicle")
        .prefetch_related("log_services__service_type")
        .order_by("-log_date", "-id")
    )


def ensure_maintenance_log_dependencies(request):
    if not Vehicle.objects.exists():
        messages.warning(request, "Add a vehicle before creating a maintenance log.")
        return redirect("vehicle_create")

    if not ServiceType.objects.exists():
        messages.warning(request, "Add a service type before creating a maintenance log.")
        return redirect("service_type_create")

    return None


def build_maintenance_log_form_context(
    *,
    form,
    formset,
    page_title,
    submit_label,
    maintenance_log=None,
):
    return {
        "form": form,
        "formset": formset,
        "page_title": page_title,
        "submit_label": submit_label,
        "maintenance_log": maintenance_log,
    }


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    next_target = request.POST.get("next") or request.GET.get("next", "")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to RevLog, {user.username}.")
            return redirect(get_post_auth_redirect(request))
    else:
        form = SignUpForm()

    context = {
        "form": form,
        "next": next_target,
    }
    return render(request, "registration/signup.html", context)


def healthcheck(request):
    return HttpResponse("ok", content_type="text/plain")


@login_required
def dashboard(request):
    total_spent = (
        MaintenanceLog.objects.aggregate(total=Sum("total_cost"))["total"] or 0
    )

    recent_log_objects = get_maintenance_log_queryset()[:10]

    recent_logs = []
    for log in recent_log_objects:
        recent_logs.append(
            {
                "vehicle_label": build_vehicle_label(log.vehicle),
                "log_date": log.log_date,
                "mileage_at_service": log.mileage_at_service,
                "shop_name": log.shop_name,
                "total_cost": log.total_cost,
                "services": build_log_service_summary(log),
            }
        )

    vehicles = Vehicle.objects.prefetch_related(
        Prefetch(
            "maintenance_logs",
            queryset=MaintenanceLog.objects.order_by("-log_date", "-id").prefetch_related(
                "log_services__service_type"
            ),
        )
    ).order_by("-year", "make", "model")

    vehicle_statuses = []
    for vehicle in vehicles:
        latest_log = next(iter(vehicle.maintenance_logs.all()), None)
        latest_services = ""

        if latest_log:
            latest_services = build_log_service_summary(latest_log)

        vehicle_statuses.append(
            {
                "vehicle": vehicle,
                "vehicle_label": build_vehicle_label(vehicle),
                "latest_log": latest_log,
                "latest_services": latest_services,
            }
        )

    context = {
        "total_vehicles": Vehicle.objects.count(),
        "total_logs": MaintenanceLog.objects.count(),
        "total_spent": total_spent,
        "total_service_types": ServiceType.objects.count(),
        "recent_logs": recent_logs,
        "vehicle_statuses": vehicle_statuses,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def maintenance_log_list(request):
    logs = get_maintenance_log_queryset()
    vehicles = Vehicle.objects.order_by("-year", "make", "model")
    selected_vehicle = request.GET.get("vehicle", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    if selected_vehicle:
        logs = logs.filter(vehicle_id=selected_vehicle)

    if date_from:
        logs = logs.filter(log_date__gte=date_from)

    if date_to:
        logs = logs.filter(log_date__lte=date_to)

    context = {
        "logs": logs,
        "vehicles": vehicles,
        "selected_vehicle": selected_vehicle,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render(request, "core/maintenance_log_list.html", context)


@login_required
def maintenance_log_create(request):
    dependency_redirect = ensure_maintenance_log_dependencies(request)
    if dependency_redirect:
        return dependency_redirect

    maintenance_log = MaintenanceLog()

    if request.method == "POST":
        form = MaintenanceLogForm(request.POST)
        formset = LogServiceFormSet(
            request.POST,
            instance=maintenance_log,
            prefix="services",
        )
        if form.is_valid() and formset.is_valid():
            maintenance_log = form.save()
            sync_vehicle_current_mileage(
                maintenance_log.vehicle,
                maintenance_log.mileage_at_service,
            )
            formset.instance = maintenance_log
            formset.save()
            messages.success(
                request,
                f"{build_vehicle_label(maintenance_log.vehicle)} maintenance log added successfully.",
            )
            return redirect("maintenance_log_list")
    else:
        form = MaintenanceLogForm(initial={"log_date": date.today()})
        formset = LogServiceFormSet(
            instance=maintenance_log,
            queryset=LogService.objects.none(),
            prefix="services",
        )

    context = build_maintenance_log_form_context(
        form=form,
        formset=formset,
        page_title="Add Maintenance Log",
        submit_label="Save Maintenance Log",
    )
    return render(request, "core/maintenance_log_form.html", context)


@login_required
def maintenance_log_update(request, maintenance_log_id):
    maintenance_log = get_object_or_404(
        get_maintenance_log_queryset(),
        pk=maintenance_log_id,
    )

    if request.method == "POST":
        form = MaintenanceLogForm(request.POST, instance=maintenance_log)
        formset = LogServiceFormSet(
            request.POST,
            instance=maintenance_log,
            prefix="services",
        )
        if form.is_valid() and formset.is_valid():
            maintenance_log = form.save()
            sync_vehicle_current_mileage(
                maintenance_log.vehicle,
                maintenance_log.mileage_at_service,
            )
            formset.save()
            messages.success(
                request,
                f"{build_vehicle_label(maintenance_log.vehicle)} maintenance log updated successfully.",
            )
            return redirect("maintenance_log_list")
    else:
        form = MaintenanceLogForm(instance=maintenance_log)
        formset = LogServiceFormSet(instance=maintenance_log, prefix="services")

    context = build_maintenance_log_form_context(
        form=form,
        formset=formset,
        page_title="Edit Maintenance Log",
        submit_label="Save Changes",
        maintenance_log=maintenance_log,
    )
    return render(request, "core/maintenance_log_form.html", context)


@login_required
def maintenance_log_delete(request, maintenance_log_id):
    maintenance_log = get_object_or_404(
        get_maintenance_log_queryset(),
        pk=maintenance_log_id,
    )

    if request.method == "POST":
        vehicle_label = build_vehicle_label(maintenance_log.vehicle)
        log_date = maintenance_log.log_date
        maintenance_log.delete()
        messages.success(
            request,
            f"{vehicle_label} maintenance log from {log_date:%b %d, %Y} deleted successfully.",
        )
        return redirect("maintenance_log_list")

    return render(
        request,
        "core/maintenance_log_confirm_delete.html",
        {"maintenance_log": maintenance_log},
    )


@login_required
def vehicle_list(request):
    vehicles = Vehicle.objects.select_related("type").order_by("-year", "make", "model")
    return render(request, "core/vehicle_list.html", {"vehicles": vehicles})


@login_required
def vehicle_create(request):
    if request.method == "POST":
        form = VehicleForm(request.POST, request.FILES)
        if form.is_valid():
            vehicle = form.save()
            messages.success(request, f"{build_vehicle_label(vehicle)} added successfully.")
            return redirect("vehicle_list")
    else:
        form = VehicleForm(initial={"year": date.today().year})

    context = {
        "form": form,
        "page_title": "Add Vehicle",
        "submit_label": "Save Vehicle",
    }
    return render(request, "core/vehicle_form.html", context)


@login_required
def vehicle_update(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)

    if request.method == "POST":
        form = VehicleForm(request.POST, request.FILES, instance=vehicle)
        if form.is_valid():
            vehicle = form.save()
            messages.success(request, f"{build_vehicle_label(vehicle)} updated successfully.")
            return redirect("vehicle_list")
    else:
        form = VehicleForm(instance=vehicle)

    context = {
        "form": form,
        "page_title": "Edit Vehicle",
        "submit_label": "Save Changes",
        "vehicle": vehicle,
    }
    return render(request, "core/vehicle_form.html", context)


@login_required
def vehicle_delete(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)

    if request.method == "POST":
        vehicle_label = build_vehicle_label(vehicle)
        vehicle.delete()
        messages.success(request, f"{vehicle_label} deleted successfully.")
        return redirect("vehicle_list")

    return render(request, "core/vehicle_confirm_delete.html", {"vehicle": vehicle})


@login_required
def service_type_list(request):
    service_types = ServiceType.objects.order_by("name")
    return render(
        request,
        "core/service_type_list.html",
        {"service_types": service_types},
    )


@login_required
def service_type_create(request):
    if request.method == "POST":
        form = ServiceTypeForm(request.POST)
        if form.is_valid():
            service_type = form.save()
            messages.success(
                request,
                f"{build_service_type_label(service_type)} added successfully.",
            )
            return redirect("service_type_list")
    else:
        form = ServiceTypeForm()

    context = {
        "form": form,
        "page_title": "Add Service Type",
        "submit_label": "Save Service Type",
    }
    return render(request, "core/service_type_form.html", context)


@login_required
def service_type_update(request, service_type_id):
    service_type = get_object_or_404(ServiceType, pk=service_type_id)

    if request.method == "POST":
        form = ServiceTypeForm(request.POST, instance=service_type)
        if form.is_valid():
            service_type = form.save()
            messages.success(
                request,
                f"{build_service_type_label(service_type)} updated successfully.",
            )
            return redirect("service_type_list")
    else:
        form = ServiceTypeForm(instance=service_type)

    context = {
        "form": form,
        "page_title": "Edit Service Type",
        "submit_label": "Save Changes",
        "service_type": service_type,
    }
    return render(request, "core/service_type_form.html", context)


@login_required
def service_type_delete(request, service_type_id):
    service_type = get_object_or_404(ServiceType, pk=service_type_id)

    if request.method == "POST":
        service_type_label = build_service_type_label(service_type)
        try:
            service_type.delete()
            messages.success(request, f"{service_type_label} deleted successfully.")
        except ProtectedError:
            messages.error(
                request,
                "This service type cannot be deleted because it is used in maintenance logs.",
            )
        return redirect("service_type_list")

    return render(
        request,
        "core/service_type_confirm_delete.html",
        {"service_type": service_type},
    )
