from datetime import date
from io import BytesIO
from pathlib import Path

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.files.uploadedfile import SimpleUploadedFile
from django.forms import BaseInlineFormSet, inlineformset_factory
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import LogService, MaintenanceLog, ServiceType, Vehicle, VehicleType


MAX_VEHICLE_PHOTO_UPLOAD_MB = 20
MAX_VEHICLE_PHOTO_UPLOAD_SIZE = MAX_VEHICLE_PHOTO_UPLOAD_MB * 1024 * 1024
VEHICLE_PHOTO_AUTO_PROCESS_THRESHOLD = 5 * 1024 * 1024
VEHICLE_PHOTO_MAX_DIMENSION = 2400
VEHICLE_PHOTO_JPEG_QUALITY = 82
VEHICLE_PHOTO_WEBP_QUALITY = 82
IMAGE_RESAMPLING = (
    Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
)
ADAPTIVE_PALETTE = (
    Image.Palette.ADAPTIVE if hasattr(Image, "Palette") else Image.ADAPTIVE
)


class SignUpForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].help_text = (
            "Use letters, numbers, and @/./+/-/_ only."
        )
        self.fields["password1"].help_text = (
            "Use at least 8 characters and avoid something too common."
        )
        self.fields["password2"].help_text = "Enter the same password again."

    def clean_username(self):
        return self.cleaned_data["username"].strip()


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
            f"Optional. Upload a JPG, PNG, WEBP, or GIF up to {MAX_VEHICLE_PHOTO_UPLOAD_MB} MB. "
            "Large photos are resized and compressed automatically."
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
        if photo is None:
            return None

        if photo.size > MAX_VEHICLE_PHOTO_UPLOAD_SIZE:
            raise forms.ValidationError(
                f"Photo must be {MAX_VEHICLE_PHOTO_UPLOAD_MB} MB or smaller."
            )

        try:
            photo.seek(0)
            with Image.open(photo) as image:
                if getattr(image, "is_animated", False):
                    return photo
                return self._process_vehicle_photo(photo, image)
        except (UnidentifiedImageError, OSError):
            raise forms.ValidationError("Upload a valid image file.")
        finally:
            photo.seek(0)

    def clean_notes(self):
        return self._clean_optional_text("notes")

    def _process_vehicle_photo(self, photo, image):
        original_name = Path(photo.name or "vehicle-photo.jpg")
        extension = original_name.suffix.lower()
        normalized_image = ImageOps.exif_transpose(image)
        processed_image = normalized_image.copy()

        should_resize = (
            processed_image.width > VEHICLE_PHOTO_MAX_DIMENSION
            or processed_image.height > VEHICLE_PHOTO_MAX_DIMENSION
        )
        should_reencode = photo.size > VEHICLE_PHOTO_AUTO_PROCESS_THRESHOLD

        if not should_resize and not should_reencode:
            return photo

        if should_resize:
            processed_image.thumbnail(
                (VEHICLE_PHOTO_MAX_DIMENSION, VEHICLE_PHOTO_MAX_DIMENSION),
                IMAGE_RESAMPLING,
            )

        output = BytesIO()
        final_name = original_name.name

        if extension in {".jpg", ".jpeg"}:
            processed_image = processed_image.convert("RGB")
            processed_image.save(
                output,
                format="JPEG",
                quality=VEHICLE_PHOTO_JPEG_QUALITY,
                optimize=True,
                progressive=True,
            )
            content_type = "image/jpeg"
            final_name = original_name.with_suffix(".jpg").name
        elif extension == ".png":
            if processed_image.mode not in {"RGB", "RGBA"}:
                processed_image = processed_image.convert("RGBA")
            processed_image.save(output, format="PNG", optimize=True)
            content_type = "image/png"
        elif extension == ".webp":
            if processed_image.mode not in {"RGB", "RGBA"}:
                processed_image = processed_image.convert("RGBA")
            processed_image.save(
                output,
                format="WEBP",
                quality=VEHICLE_PHOTO_WEBP_QUALITY,
                method=6,
            )
            content_type = "image/webp"
        elif extension == ".gif":
            processed_image = processed_image.convert("P", palette=ADAPTIVE_PALETTE)
            processed_image.save(output, format="GIF", optimize=True)
            content_type = "image/gif"
        else:
            return photo

        processed_bytes = output.getvalue()
        if not should_resize and len(processed_bytes) >= photo.size:
            return photo

        return SimpleUploadedFile(
            final_name,
            processed_bytes,
            content_type=content_type,
        )

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
