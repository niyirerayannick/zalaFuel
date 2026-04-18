from django import forms

from accounts.models import User
from transport.messaging.models import DriverManagerMessage


class DriverProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "phone", "email", "profile_photo"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_class = (
            "mt-2 block w-full rounded-2xl border border-emerald-900/10 bg-white/90 "
            "px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 "
            "focus:outline-none focus:ring-4 focus:ring-emerald-500/15"
        )
        for name, field in self.fields.items():
            if name == "profile_photo":
                field.widget.attrs.update(
                    {
                        "class": "mt-2 block w-full text-sm text-slate-500 file:mr-4 file:rounded-full file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:font-semibold file:text-white hover:file:bg-emerald-700",
                        "accept": "image/*",
                    }
                )
            else:
                field.widget.attrs.update({"class": base_class})

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email


class DriverMessageForm(forms.ModelForm):
    class Meta:
        model = DriverManagerMessage
        fields = ["body"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].widget.attrs.update(
            {
                "class": "min-h-[48px] w-full resize-none rounded-3xl border border-emerald-900/10 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-emerald-600 focus:bg-white focus:outline-none focus:ring-4 focus:ring-emerald-500/15",
                "placeholder": "Message",
                "rows": 2,
            }
        )

    def clean_body(self):
        body = (self.cleaned_data.get("body") or "").strip()
        if not body:
            raise forms.ValidationError("Enter a message before sending.")
        return body
