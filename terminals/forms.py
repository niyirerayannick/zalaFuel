from django import forms

from accounts.models import User

from .models import Terminal


class TerminalForm(forms.ModelForm):
    manager = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        empty_label="Select manager",
    )

    class Meta:
        model = Terminal
        fields = ["name", "code", "location", "status", "capacity_liters", "manager", "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = User.objects.filter(
            is_active=True,
            role__in=[
                User.Role.SUPERADMIN,
                User.Role.ADMIN,
                User.Role.STATION_MANAGER,
                User.Role.SUPERVISOR,
            ],
        ).order_by("full_name", "email")
        self.fields["manager"].label_from_instance = lambda user: f"{user.full_name} ({user.email})"
        for field in self.fields.values():
            field.widget.attrs.update(
                {
                    "class": "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-blue-200 focus:border-blue-600"
                }
            )
        self.fields["manager"].help_text = "Managers must exist in the user system before they can be assigned to a terminal."
        self.fields["notes"].widget.attrs["rows"] = 3

    def save(self, commit=True):
        instance = super().save(commit=False)
        manager = self.cleaned_data.get("manager")
        instance.manager = manager
        instance.manager_name = manager.full_name if manager else ""
        if commit:
            instance.save()
        return instance
