from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm
from django.core.exceptions import ValidationError

from .models import UserProfile, SystemSettings
from .rbac import SYSTEM_ROLE_CHOICES, current_system_role, sync_user_to_system_role
from stations.models import Station

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autofocus": True}))
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )


class UserCreationForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    national_id = forms.CharField(required=False)
    emergency_contact = forms.CharField(required=False)
    license_number = forms.CharField(required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "phone",
            "staff_id",
            "role",
            "assigned_station",
            "profile_photo",
            "is_active",
            "is_staff",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_staff_id(self):
        staff_id = (self.cleaned_data.get("staff_id") or "").strip()
        if staff_id and User.objects.filter(staff_id__iexact=staff_id).exists():
            raise ValidationError("A user with this staff ID already exists.")
        return staff_id or None

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        role = cleaned_data.get("role")
        assigned_station = cleaned_data.get("assigned_station")
        if role in {"Station Manager", "Supervisor", "Pump Attendant", "Accountant"} and not assigned_station:
            self.add_error("assigned_station", "Assigned station is required for station staff roles.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].lower()
        user.set_password(self.cleaned_data["password1"])
        user.must_change_password = True
        selected_role = self.cleaned_data["role"]
        sync_user_to_system_role(user, selected_role)
        if commit:
            user.save()
            sync_user_to_system_role(user, selected_role)
            self._save_profile(user)
        return user

    def _save_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field in ("address", "national_id", "emergency_contact", "license_number"):
            setattr(profile, field, self.cleaned_data.get(field) or "")
        profile.save()

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        station_queryset = kwargs.pop("station_queryset", None)
        role_choices = kwargs.pop("role_choices", None)
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices or SYSTEM_ROLE_CHOICES
        self.fields["assigned_station"].queryset = station_queryset or Station.objects.filter(is_active=True).order_by("name")
        self.fields["assigned_station"].empty_label = "Select station"
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        for name in ("is_active", "is_staff"):
            self.fields[name].widget.attrs["class"] = "h-4 w-4 rounded border-slate-300 text-green-700 focus:ring-green-600"


class UserUpdateForm(forms.ModelForm):
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    national_id = forms.CharField(required=False)
    emergency_contact = forms.CharField(required=False)
    license_number = forms.CharField(required=False)

    class Meta:
        model = User
        fields = (
            "email",
            "full_name",
            "phone",
            "staff_id",
            "role",
            "assigned_station",
            "profile_photo",
            "is_active",
            "is_staff",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean_staff_id(self):
        staff_id = (self.cleaned_data.get("staff_id") or "").strip()
        qs = User.objects.filter(staff_id__iexact=staff_id).exclude(pk=self.instance.pk)
        if staff_id and qs.exists():
            raise ValidationError("A user with this staff ID already exists.")
        return staff_id or None

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        assigned_station = cleaned_data.get("assigned_station")
        if role in {"Station Manager", "Supervisor", "Pump Attendant", "Accountant"} and not assigned_station:
            self.add_error("assigned_station", "Assigned station is required for station staff roles.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        station_queryset = kwargs.pop("station_queryset", None)
        role_choices = kwargs.pop("role_choices", None)
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices or SYSTEM_ROLE_CHOICES
        self.fields["assigned_station"].queryset = station_queryset or Station.objects.filter(is_active=True).order_by("name")
        self.fields["assigned_station"].empty_label = "Select station"
        if self.instance and self.instance.pk:
            self.initial["role"] = current_system_role(self.instance)
            try:
                profile = self.instance.profile
            except (UserProfile.DoesNotExist, AttributeError):
                profile = None
            if profile:
                for field in ("address", "national_id", "emergency_contact", "license_number"):
                    self.initial[field] = getattr(profile, field, "")
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )

    def save(self, commit=True):
        user = super().save(commit=False)
        selected_role = self.cleaned_data["role"]
        sync_user_to_system_role(user, selected_role)
        if commit:
            user.save()
            sync_user_to_system_role(user, selected_role)
            self._save_profile(user)
        return user

    def _save_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        for field in ("address", "national_id", "emergency_contact", "license_number"):
            setattr(profile, field, self.cleaned_data.get(field) or "")
        profile.save()


class ForgotPasswordRequestForm(forms.Form):
    email = forms.EmailField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "class": "w-full rounded-xl border border-slate-300 bg-white/95 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
                "placeholder": "name@company.com",
                "autocomplete": "email",
            }
        )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()


class PasswordResetCodeForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].widget.attrs.update(
            {
                "class": "w-full rounded-xl border border-slate-300 bg-white/95 px-4 py-3 text-center text-lg font-semibold tracking-[0.4em] text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
                "placeholder": "000000",
                "autocomplete": "one-time-code",
                "inputmode": "numeric",
            }
        )

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().replace(" ", "")
        if not code.isdigit():
            raise ValidationError("Enter the 6-digit verification code.")
        return code


class LoginVerificationCodeForm(PasswordResetCodeForm):
    pass


class PasswordResetNewPasswordForm(DjangoSetPasswordForm):
    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "w-full rounded-xl border border-slate-300 bg-white/95 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
                }
            )
        self.fields["new_password1"].widget.attrs["placeholder"] = "Create a new password"
        self.fields["new_password2"].widget.attrs["placeholder"] = "Confirm your new password"


class PasswordChangeForm(DjangoPasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "w-full rounded-xl border border-slate-300 bg-white/95 px-4 py-3 text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-600",
                }
            )
        self.fields["old_password"].widget.attrs["placeholder"] = "Current password"
        self.fields["new_password1"].widget.attrs["placeholder"] = "New password"
        self.fields["new_password2"].widget.attrs["placeholder"] = "Confirm new password"


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("address", "national_id", "emergency_contact", "license_number")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )


class SystemSettingsForm(forms.ModelForm):
    """Form for updating system settings"""

    CURRENCY_CHOICES = [
        ("USD", "US Dollar ($)"),
        ("EUR", "Euro (EUR)"),
        ("GBP", "British Pound (GBP)"),
        ("RWF", "Rwandan Franc (Fr)"),
        ("KES", "Kenyan Shilling (KSh)"),
        ("UGX", "Ugandan Shilling (USh)"),
        ("TZS", "Tanzanian Shilling (TSh)"),
        ("SLE", "Sierra Leone Leone (Le)"),
    ]

    CURRENCY_SYMBOL_MAP = {
        "USD": "$",
        "EUR": "EUR",
        "GBP": "GBP",
        "RWF": "FRw",
        "KES": "KSh",
        "UGX": "USh",
        "TZS": "TSh",
        "SLE": "Le",
    }
    
    class Meta:
        model = SystemSettings
        fields = [
            'company_name',
            'company_logo', 
            'primary_color',
            'currency',
            'currency_symbol',
            'usd_bank_name',
            'usd_account_name',
            'usd_account_number',
            'rwf_bank_name',
            'rwf_account_name',
            'rwf_account_number',
            'petrol_unit_price',
            'diesel_unit_price',
            'timezone_setting',
            'date_format',
            'language'
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'Enter company name'
            }),
            'company_logo': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-slate-500 file:mr-4 file:rounded-lg file:border-0 file:bg-green-50 file:px-4 file:py-2.5 file:text-sm file:font-semibold file:text-green-700 hover:file:bg-green-100'
            }),
            'primary_color': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600'
            }),
            'currency': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600'
            }),
            'currency_symbol': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': '$'
            }),
            'usd_bank_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'USD bank name'
            }),
            'usd_account_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'USD account name'
            }),
            'usd_account_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'USD account number'
            }),
            'rwf_bank_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'RWF bank name'
            }),
            'rwf_account_name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'RWF account name'
            }),
            'rwf_account_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'RWF account number'
            }),
            'petrol_unit_price': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'diesel_unit_price': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'timezone_setting': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600',
                'placeholder': 'UTC'
            }),
            'date_format': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600'
            }),
            'language': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-xl border-slate-300 bg-slate-50 px-4 py-3 text-sm shadow-sm focus:border-green-600 focus:bg-white focus:ring-green-600'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].choices = self.CURRENCY_CHOICES
        self.fields["currency_symbol"].required = False
        self.fields["usd_bank_name"].required = False
        self.fields["usd_account_name"].required = False
        self.fields["usd_account_number"].required = False
        self.fields["rwf_bank_name"].required = False
        self.fields["rwf_account_name"].required = False
        self.fields["rwf_account_number"].required = False
        self.fields["petrol_unit_price"].required = False
        self.fields["diesel_unit_price"].required = False
        self.fields["company_name"].widget.attrs.setdefault("maxlength", "255")
        self.fields["currency_symbol"].widget.attrs.setdefault("maxlength", "5")
        self.fields["usd_bank_name"].widget.attrs.setdefault("maxlength", "120")
        self.fields["usd_account_name"].widget.attrs.setdefault("maxlength", "120")
        self.fields["usd_account_number"].widget.attrs.setdefault("maxlength", "120")
        self.fields["rwf_bank_name"].widget.attrs.setdefault("maxlength", "120")
        self.fields["rwf_account_name"].widget.attrs.setdefault("maxlength", "120")
        self.fields["rwf_account_number"].widget.attrs.setdefault("maxlength", "120")
        self.fields["timezone_setting"].widget.attrs.setdefault("maxlength", "50")

    def clean_petrol_unit_price(self):
        price = self.cleaned_data.get("petrol_unit_price") or 0
        if price < 0:
            raise ValidationError("Petrol unit price cannot be negative.")
        return price

    def clean_diesel_unit_price(self):
        price = self.cleaned_data.get("diesel_unit_price") or 0
        if price < 0:
            raise ValidationError("Diesel unit price cannot be negative.")
        return price

    def clean_company_name(self):
        company_name = (self.cleaned_data.get("company_name") or "").strip()
        if not company_name:
            raise ValidationError("Company name is required.")
        return company_name

    def clean_currency_symbol(self):
        symbol = (self.cleaned_data.get("currency_symbol") or "").strip()
        currency = self.cleaned_data.get("currency") or getattr(self.instance, "currency", SystemSettings.Currency.USD)
        if not symbol:
            return self.CURRENCY_SYMBOL_MAP.get(currency, currency)
        return symbol

    def clean_timezone_setting(self):
        timezone_setting = (self.cleaned_data.get("timezone_setting") or "").strip()
        if not timezone_setting:
            raise ValidationError("Timezone is required.")
        return timezone_setting

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.currency_symbol:
            instance.currency_symbol = self.CURRENCY_SYMBOL_MAP.get(instance.currency, instance.currency)
        if commit:
            instance.save()
        return instance
