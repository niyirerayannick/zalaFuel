import uuid
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .currency import CURRENCY_SYMBOLS
from .managers import CustomUserManager


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPERADMIN = "superadmin", "SuperAdmin"
        ADMIN = "admin", "Admin"
        STATION_MANAGER = "station_manager", "Station Manager"
        SUPERVISOR = "supervisor", "Supervisor"
        PUMP_ATTENDANT = "pump_attendant", "Pump Attendant"
        ACCOUNTANT = "accountant", "Accountant"
        CLIENT = "client", "Customer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    staff_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    phone = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r"^[0-9+()\-\s]{7,20}$")],
        blank=True,
    )
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ADMIN)
    assigned_station = models.ForeignKey(
        "stations.Station",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_members",
    )
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    session_invalid_before = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    objects = CustomUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"


class UserProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    address = models.TextField(blank=True)
    national_id = models.CharField(max_length=50, blank=True)
    emergency_contact = models.CharField(max_length=120, blank=True)
    license_number = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"Profile - {self.user.email}"


class ActivityLog(models.Model):
    """Track user activities for audit purposes"""
    class ActionType(models.TextChoices):
        LOGIN = "login", "Login"
        LOGOUT = "logout", "Logout" 
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VIEW = "view", "View"
        EXPORT = "export", "Export"
        
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activity_logs')
    action = models.CharField(max_length=20, choices=ActionType.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.user.full_name} - {self.get_action_display()} - {self.created_at}"


class PasswordResetVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_reset_verifications")
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["expires_at", "used_at"]),
        ]

    def __str__(self):
        return f"Password reset verification for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @classmethod
    def issue_for_user(cls, user, *, ip_address=None, lifetime_minutes=10):
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        raw_code = f"{secrets.randbelow(1000000):06d}"
        verification = cls.objects.create(
            user=user,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
            ip_address=ip_address,
        )
        verification.raw_code = raw_code
        return verification

    def check_code(self, code):
        if self.is_used or self.is_expired:
            return False
        self.attempt_count = (self.attempt_count or 0) + 1
        self.save(update_fields=["attempt_count"])
        return check_password(code, self.code_hash)


class LoginVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_verifications")
    code_hash = models.CharField(max_length=255)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["expires_at", "used_at"]),
        ]

    def __str__(self):
        return f"Login verification for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @classmethod
    def issue_for_user(cls, user, *, ip_address=None, lifetime_minutes=10):
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
        raw_code = f"{secrets.randbelow(1000000):06d}"
        verification = cls.objects.create(
            user=user,
            code_hash=make_password(raw_code),
            expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
            ip_address=ip_address,
        )
        verification.raw_code = raw_code
        return verification

    def check_code(self, code):
        if self.is_used or self.is_expired:
            return False
        self.attempt_count = (self.attempt_count or 0) + 1
        self.save(update_fields=["attempt_count"])
        return check_password(code, self.code_hash)


class RolePermission(models.Model):
    """Custom role and permission management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=[
        ('superadmin', 'SuperAdmin'),
        ('admin', 'Admin'),
        ('station_manager', 'Station Manager'),
        ('supervisor', 'Supervisor'),
        ('pump_attendant', 'Pump Attendant'),
        ('accountant', 'Accountant'),
    ])
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    granted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='permissions_granted')
    granted_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ['role', 'permission']
        
    def __str__(self):
        return f"{self.role} - {self.permission.name}"


class SystemSettings(models.Model):
    """System-wide settings for the application"""
    CACHE_KEY = "accounts.system_settings.current"

    class ColorTheme(models.TextChoices):
        BLUE = "blue", "Blue Theme"
        GREEN = "green", "Green Theme"
        PURPLE = "purple", "Purple Theme"
        RED = "red", "Red Theme"
        ORANGE = "orange", "Orange Theme"
        
    class Currency(models.TextChoices):
        USD = "USD", "US Dollar ($)"
        EUR = "EUR", "Euro (â‚¬)"
        GBP = "GBP", "British Pound (Â£)"
        RWF = "RWF", "Rwandan Franc (Fr)"
        KES = "KES", "Kenyan Shilling (KSh)"
        UGX = "UGX", "Ugandan Shilling (USh)"
        TZS = "TZS", "Tanzanian Shilling (TSh)"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(
        max_length=255,
        default="ZALA/ECO ENERGY",
    )
    company_logo = models.ImageField(upload_to="settings/", blank=True, null=True)
    primary_color = models.CharField(
        max_length=20, 
        choices=ColorTheme.choices, 
        default=ColorTheme.BLUE,
        help_text="Primary color theme for the application"
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=getattr(settings, "DEFAULT_CURRENCY", Currency.USD),
        help_text="Default currency for financial calculations"
    )
    currency_symbol = models.CharField(
        max_length=5,
        default=CURRENCY_SYMBOLS.get(getattr(settings, "DEFAULT_CURRENCY", Currency.USD), "$"),
    )
    usd_bank_name = models.CharField(max_length=120, blank=True)
    usd_account_name = models.CharField(max_length=120, blank=True)
    usd_account_number = models.CharField(max_length=120, blank=True)
    rwf_bank_name = models.CharField(max_length=120, blank=True)
    rwf_account_name = models.CharField(max_length=120, blank=True)
    rwf_account_number = models.CharField(max_length=120, blank=True)
    petrol_unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Default POS unit price per liter for petrol",
    )
    diesel_unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Default POS unit price per liter for diesel",
    )
    exchange_rate_cache = models.TextField(
        blank=True, default="",
        help_text="JSON cache for exchange rates â€” auto-managed",
    )
    timezone_setting = models.CharField(max_length=50, default="UTC")
    date_format = models.CharField(
        max_length=20,
        choices=[
            ('Y-m-d', 'YYYY-MM-DD'),
            ('d/m/Y', 'DD/MM/YYYY'),
            ('m/d/Y', 'MM/DD/YYYY'),
            ('d-m-Y', 'DD-MM-YYYY'),
        ],
        default='Y-m-d'
    )
    language = models.CharField(
        max_length=10,
        choices=[
            ('en', 'English'),
            ('fr', 'French'),
            ('sw', 'Swahili'),
            ('rw', 'Kinyarwanda'),
        ],
        default='en'
    )
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='settings_updated')
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
        
    def __str__(self):
        return f"System Settings - {self.company_name}"

    @classmethod
    def _cache_get(cls):
        try:
            return cache.get(cls.CACHE_KEY)
        except Exception:
            return None

    @classmethod
    def _cache_set(cls, value):
        try:
            cache.set(cls.CACHE_KEY, value, 300)
        except Exception:
            pass

    @classmethod
    def _cache_delete(cls):
        try:
            cache.delete(cls.CACHE_KEY)
        except Exception:
            pass

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)
        self._cache_delete()
        return result

    def delete(self, *args, **kwargs):
        self._cache_delete()
        return super().delete(*args, **kwargs)
        
    @classmethod
    def get_settings(cls):
        """Get the current system settings, create if doesn't exist"""
        cached_settings = cls._cache_get()
        if cached_settings is not None:
            return cached_settings

        system_settings = cls.objects.first()
        if system_settings is None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admin_user = User.objects.filter(
                role__in=['superadmin', 'admin']
            ).first()
            if admin_user is None:
                admin_user = User.objects.first()
                if admin_user:
                    system_settings = cls.objects.create(
                        company_name="ZALA/ECO ENERGY",
                        primary_color=cls.ColorTheme.BLUE,
                        currency=getattr(settings, "DEFAULT_CURRENCY", cls.Currency.USD),
                    currency_symbol=CURRENCY_SYMBOLS.get(getattr(settings, "DEFAULT_CURRENCY", cls.Currency.USD), "$"),
                        updated_by=admin_user,
                    )
        cls._cache_set(system_settings)
        return system_settings
