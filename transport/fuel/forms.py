from django import forms
from .models import FuelRequest, FuelDocument
from transport.trips.models import Trip
from transport.drivers.models import Driver

class FuelRequestForm(forms.ModelForm):
    receipt = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        driver_user = kwargs.pop("driver_user", None)
        trip = kwargs.pop("trip", None)
        super().__init__(*args, **kwargs)

        if driver_user is None:
            self.fields["trip"].queryset = Trip.objects.none()
        else:
            driver = Driver.objects.filter(user=driver_user).first()
            if driver is None:
                self.fields["trip"].queryset = Trip.objects.none()
            else:
                self.fields["trip"].queryset = Trip.objects.filter(
                    driver=driver,
                    status=Trip.TripStatus.IN_TRANSIT,
                ).order_by("-created_at")

        self.fields["trip"].widget.attrs.update({"class": "hidden"})
        self.fields["station"].widget.attrs.update({
            "class": "mt-2 block w-full rounded-2xl border border-emerald-900/10 bg-white/90 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-4 focus:ring-emerald-500/15"
        })
        self.fields["amount"].widget.attrs.update({
            "class": "mt-2 block w-full rounded-2xl border border-emerald-900/10 bg-white/90 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-4 focus:ring-emerald-500/15",
            "placeholder": "Enter fuel amount",
        })
        self.fields["notes"].widget.attrs.update({
            "class": "mt-2 block min-h-24 w-full rounded-2xl border border-emerald-900/10 bg-white/90 px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-emerald-600 focus:outline-none focus:ring-4 focus:ring-emerald-500/15",
            "placeholder": "Add delivery or station notes",
        })
        self.fields["receipt"].widget.attrs.update({
            "class": "sr-only",
            "accept": "image/*,.pdf",
            "x-on:change": "selectedFile = $event.target.files.length ? $event.target.files[0].name : ''",
        })
        self.fields["trip"].required = False
        if trip is not None:
            self.fields["trip"].initial = trip.pk

    class Meta:
        model = FuelRequest
        fields = ["trip", "station", "amount", "notes"]

    def clean_trip(self):
        trip = self.cleaned_data.get("trip")
        if trip is None:
            raise forms.ValidationError("An active trip is required for a fuel request.")
        if trip.status != Trip.TripStatus.IN_TRANSIT:
            raise forms.ValidationError("Fuel requests are only allowed for active trips.")
        return trip

class FuelDocumentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document"].widget.attrs.update(
            {
                "class": "sr-only",
                "accept": "image/*,.pdf",
                "x-ref": "fileInput",
                "x-on:change": "selectedFile = $event.target.files.length ? $event.target.files[0].name : ''",
            }
        )

    class Meta:
        model = FuelDocument
        fields = ['document']
