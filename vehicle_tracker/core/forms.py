from datetime import date

from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import LogService, MaintenanceLog, ServiceType, Vehicle, VehicleType


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "year",
            "make",
            "model",
            "nickname",
            "type",
            "color",
            "current_mileage",
            "vin",
            "photo",
            "notes",
        ]
        widgets = {
            "year": forms.NumberInput(attrs={"min": 1900, "max": date.today().year + 1}),
            "current_mileage": forms.NumberInput(attrs={"min": 0}),
            "photo": forms.FileInput(attrs={"accept": "image/*"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].queryset = VehicleType.objects.order_by("name")
        self.fields["photo"].help_text = (
            "Optional. Upload a JPG, PNG, WEBP, or GIF up to 5 MB."
        )

    def clean_year(self):
        year = self.cleaned_data["year"]
        max_year = date.today().year + 1
        if year < 1900 or year > max_year:
            raise forms.ValidationError(f"Year must be between 1900 and {max_year}.")
        return year

    def clean_make(self):
        return self.cleaned_data["make"].strip()

    def clean_model(self):
        return self.cleaned_data["model"].strip()

    def clean_current_mileage(self):
        mileage = self.cleaned_data.get("current_mileage")
        if mileage is not None and mileage < 0:
            raise forms.ValidationError("Mileage must be 0 or greater.")
        return mileage

    def clean_nickname(self):
        return self._clean_optional_text("nickname")

    def clean_color(self):
        return self._clean_optional_text("color")

    def clean_vin(self):
        return self._clean_optional_text("vin")

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo is not None and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Photo must be 5 MB or smaller.")
        return photo

    def clean_notes(self):
        return self._clean_optional_text("notes")

    def _clean_optional_text(self, field_name):
        value = self.cleaned_data.get(field_name)
        if value is None:
            return None

        value = value.strip()
        return value or None


class ServiceTypeForm(forms.ModelForm):
    class Meta:
        model = ServiceType
        fields = [
            "name",
            "description",
            "default_interval_miles",
            "default_interval_days",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "default_interval_miles": forms.NumberInput(attrs={"min": 0, "step": 500}),
            "default_interval_days": forms.NumberInput(attrs={"min": 0, "step": 30}),
        }

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean_description(self):
        value = self.cleaned_data.get("description")
        if value is None:
            return None

        value = value.strip()
        return value or None

    def clean_default_interval_miles(self):
        miles = self.cleaned_data.get("default_interval_miles")
        if miles in (None, 0):
            return None
        if miles < 0:
            raise forms.ValidationError("Interval miles must be 0 or greater.")
        return miles

    def clean_default_interval_days(self):
        days = self.cleaned_data.get("default_interval_days")
        if days in (None, 0):
            return None
        if days < 0:
            raise forms.ValidationError("Interval days must be 0 or greater.")
        return days


class MaintenanceLogForm(forms.ModelForm):
    class Meta:
        model = MaintenanceLog
        fields = [
            "vehicle",
            "log_date",
            "mileage_at_service",
            "shop_name",
            "total_cost",
            "notes",
        ]
        widgets = {
            "log_date": forms.DateInput(attrs={"type": "date"}),
            "mileage_at_service": forms.NumberInput(attrs={"min": 0}),
            "total_cost": forms.NumberInput(attrs={"min": 0, "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.order_by("-year", "make", "model")

    def clean_log_date(self):
        log_date = self.cleaned_data["log_date"]
        if log_date > date.today():
            raise forms.ValidationError("Service date cannot be in the future.")
        return log_date

    def clean_mileage_at_service(self):
        mileage = self.cleaned_data.get("mileage_at_service")
        if mileage is not None and mileage < 0:
            raise forms.ValidationError("Mileage must be 0 or greater.")
        return mileage

    def clean_total_cost(self):
        total_cost = self.cleaned_data.get("total_cost")
        if total_cost is not None and total_cost < 0:
            raise forms.ValidationError("Total cost must be 0 or greater.")
        return total_cost

    def clean_shop_name(self):
        return self._clean_optional_text("shop_name")

    def clean_notes(self):
        return self._clean_optional_text("notes")

    def _clean_optional_text(self, field_name):
        value = self.cleaned_data.get(field_name)
        if value is None:
            return None

        value = value.strip()
        return value or None


class LogServiceForm(forms.ModelForm):
    class Meta:
        model = LogService
        fields = ["service_type", "notes"]
        widgets = {
            "notes": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["service_type"].queryset = ServiceType.objects.order_by("name")

    def clean_notes(self):
        value = self.cleaned_data.get("notes")
        if value is None:
            return None

        value = value.strip()
        return value or None


class BaseLogServiceFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        seen_service_type_ids = set()
        active_forms = 0

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE"):
                continue

            service_type = form.cleaned_data.get("service_type")
            notes = form.cleaned_data.get("notes")
            has_details = bool(notes)

            if not service_type and not has_details:
                continue

            if not service_type and has_details:
                form.add_error("service_type", "Choose a service type for this row.")
                continue

            active_forms += 1

            if service_type.pk in seen_service_type_ids:
                form.add_error("service_type", "Each service type can only be added once.")
            else:
                seen_service_type_ids.add(service_type.pk)

        if active_forms == 0:
            raise forms.ValidationError(
                "Add at least one service performed for this maintenance log."
            )


LogServiceFormSet = inlineformset_factory(
    MaintenanceLog,
    LogService,
    form=LogServiceForm,
    formset=BaseLogServiceFormSet,
    extra=5,
    can_delete=True,
)
