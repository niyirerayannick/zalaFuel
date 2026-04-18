from django import forms

from sales.models import Customer
from sales.models import CreditPayment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "phone", "email", "customer_type", "credit_limit", "address", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "Customer name"}),
            "phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "Phone number"}),
            "email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "customer@example.com"}),
            "customer_type": forms.Select(attrs={"class": "form-select"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "address": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Customer address"}),
            "notes": forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Internal notes"}),
        }

    def clean_credit_limit(self):
        credit_limit = self.cleaned_data.get("credit_limit") or 0
        if credit_limit < 0:
            raise forms.ValidationError("Credit limit cannot be negative.")
        return credit_limit

    def save(self, commit=True):
        customer = super().save(commit=False)
        customer.is_credit_allowed = customer.customer_type == Customer.CustomerType.CREDIT
        if not customer.is_credit_allowed:
            customer.credit_limit = 0
        if commit:
            customer.save()
        return customer


class CreditPaymentForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0.01"}),
    )
    method = forms.ChoiceField(
        choices=CreditPayment.Method.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    reference = forms.CharField(
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Receipt / bank reference"}),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-input", "rows": 3, "placeholder": "Settlement notes"}),
    )

    def __init__(self, *args, customer=None, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)
        if customer is not None:
            self.fields["amount"].help_text = f"Outstanding balance: {customer.current_balance:.2f}"

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if self.customer and amount and amount > self.customer.current_balance:
            raise forms.ValidationError("Payment amount cannot exceed the current outstanding balance.")
        return amount
