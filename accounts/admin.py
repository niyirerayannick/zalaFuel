from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import UserCreationForm, UserUpdateForm
from .models import (
    ActivityLog,
    LoginVerification,
    PasswordResetVerification,
    RolePermission,
    SystemSettings,
    User,
    UserProfile,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserCreationForm
    form = UserUpdateForm
    model = User

    list_display = (
        "email",
        "full_name",
        "role",
        "phone",
        "is_active",
        "is_staff",
        "created_at",
    )
    list_filter = ("role", "is_active", "is_staff", "is_superuser", "created_at")
    search_fields = ("email", "full_name", "phone")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "last_login")

    fieldsets = (
        (
            "Authentication",
            {
                "fields": ("email", "password"),
            },
        ),
        (
            "Personal Info",
            {
                "fields": ("full_name", "staff_id", "phone", "role", "assigned_station", "profile_photo"),
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        ("Important Dates", {"fields": ("last_login", "created_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "staff_id",
                    "phone",
                    "role",
                    "assigned_station",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "national_id", "license_number", "emergency_contact")
    search_fields = ("user__email", "user__full_name", "national_id", "license_number")
    list_select_related = ("user",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "description", "ip_address", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("user__email", "user__full_name", "description")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "granted_by", "granted_at")
    list_filter = ("role", "granted_at")
    search_fields = ("role", "permission__name")


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("company_name", "primary_color", "currency", "usd_bank_name", "rwf_bank_name", "updated_by", "updated_at")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Company Information", {
            "fields": ("company_name", "company_logo")
        }),
        ("Appearance", {
            "fields": ("primary_color",)
        }),
        ("Localization", {
            "fields": ("currency", "currency_symbol", "timezone_setting", "date_format", "language")
        }),
        ("Payment Information", {
            "fields": (
                "usd_bank_name",
                "usd_account_name",
                "usd_account_number",
                "rwf_bank_name",
                "rwf_account_name",
                "rwf_account_number",
            )
        }),
        ("System Info", {
            "fields": ("updated_by", "created_at", "updated_at"),
            "classes": ("collapse",)
        })
    )


@admin.register(PasswordResetVerification)
class PasswordResetVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "attempt_count", "ip_address", "created_at")
    list_filter = ("used_at", "expires_at", "created_at")
    search_fields = ("user__email", "user__full_name", "ip_address")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "attempt_count")


@admin.register(LoginVerification)
class LoginVerificationAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "attempt_count", "ip_address", "created_at")
    list_filter = ("used_at", "expires_at", "created_at")
    search_fields = ("user__email", "user__full_name", "ip_address")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "attempt_count")
