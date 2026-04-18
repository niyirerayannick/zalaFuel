import json

from django import forms
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta

from accounts.currency import CURRENCY_SYMBOLS
from .models import Order, OrderNote, OrderDocument
from transport.customers.models import Customer
from transport.routes.models import Route
from transport.trips.models import CargoCategory, ensure_default_cargo_categories
from transport.vehicles.models import Vehicle
from transport.drivers.models import Driver
from accounts.models import SystemSettings


class OrderForm(forms.ModelForm):
    """Form for creating and editing orders"""
    CATEGORY_COMMODITY_MAP = {
        "fuel": [
            Order.CommodityType.DIESEL,
            Order.CommodityType.PETROL,
            Order.CommodityType.JET_A1,
            Order.CommodityType.BITUMEN,
        ],
        "food commodity": [Order.CommodityType.FOOD_BEVERAGE],
        "general cargo": [
            Order.CommodityType.GENERAL_CARGO,
            Order.CommodityType.ELECTRONICS,
            Order.CommodityType.TEXTILES,
            Order.CommodityType.MACHINERY,
            Order.CommodityType.CHEMICALS,
            Order.CommodityType.CONSTRUCTION,
            Order.CommodityType.AUTOMOTIVE,
            Order.CommodityType.PHARMACEUTICALS,
            Order.CommodityType.FURNITURE,
            Order.CommodityType.OTHER,
        ],
    }
    
    class Meta:
        model = Order
        fields = [
            'customer', 'cargo_category', 'commodity_type', 'commodity_description',
            'total_quantity', 'unit', 'weight_kg', 'route', 'pickup_address',
            'delivery_address', 'pickup_contact', 'delivery_contact',
            'requested_pickup_date', 'requested_delivery_date', 'quoted_price', 'payment_terms',
            'special_instructions', 'requires_insurance',
            'requires_special_handling', 'fragile_items', 'priority_level'
        ]
        
        widgets = {
            'customer': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'cargo_category': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'commodity_type': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'commodity_description': forms.Textarea(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 3
            }),
            'unit': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'weight_kg': forms.NumberInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0.01'
            }),
            'total_quantity': forms.NumberInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0.01'
            }),
            'route': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'pickup_address': forms.Textarea(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 2
            }),
            'delivery_address': forms.Textarea(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 2
            }),
            'pickup_contact': forms.TextInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Name and phone number'
            }),
            'delivery_contact': forms.TextInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Name and phone number'
            }),
            'requested_pickup_date': forms.DateTimeInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'type': 'datetime-local'
            }),
            'requested_delivery_date': forms.DateTimeInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'type': 'datetime-local'
            }),
            'quoted_price': forms.NumberInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01'
            }),
            'payment_terms': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'special_instructions': forms.Textarea(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 3
            }),
            'priority_level': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ensure_default_cargo_categories()
        self.fields["cargo_category"].queryset = CargoCategory.objects.filter(is_active=True).order_by("name")
        self.fields["unit"].queryset = self._unit_queryset()
        self.fields["unit"].empty_label = "Select unit"
        self.fields["unit"].required = True
        self._set_commodity_choices()
        self.fields["total_quantity"].label = "Total Quantity"
        self.fields["weight_kg"].label = "Weight (kg)"
        self.fields["weight_kg"].required = True
        self.fields["pickup_contact"].required = False
        self.fields["delivery_contact"].required = False
        self.fields["special_instructions"].required = False
        
        # Set minimum dates for pickup and delivery
        min_date = timezone.now()
        self.fields['requested_pickup_date'].widget.attrs['min'] = min_date.strftime('%Y-%m-%dT%H:%M')
        self.fields['requested_delivery_date'].widget.attrs['min'] = min_date.strftime('%Y-%m-%dT%H:%M')
        
        # Add help text
        self.fields['cargo_category'].help_text = "Cargo category used for operations and reporting."
        self.fields['total_quantity'].help_text = "Primary cargo quantity used for shipment preparation and remaining-balance checks."
        self.fields['unit'].help_text = "Select the unit for the total quantity."
        self.fields['weight_kg'].help_text = "Total cargo weight in kilograms."
        currency_code, currency_symbol = self._currency_context()
        self.fields['quoted_price'].help_text = f"Price quoted to customer in system currency ({currency_code} {currency_symbol})."
        self.fields['payment_terms'].help_text = "Commercial payment period agreed with the customer."
        self.fields["quoted_price"].widget.attrs["placeholder"] = f"{currency_symbol} 0.00"
        self.fields["quoted_price"].widget.attrs["data-currency-symbol"] = currency_symbol
        self.fields["total_quantity"].widget.attrs["data-unit-target"] = "total"
        unit_map = {
            str(unit.pk): {
                "category": unit.measurement_category,
                "symbol": unit.symbol,
            }
            for unit in self.fields["unit"].queryset
        }
        self.fields["unit"].widget.attrs["data-unit-map"] = json.dumps(unit_map)

    def _unit_queryset(self):
        from .models import Unit

        return Unit.objects.filter(is_active=True).order_by("name")

    def _currency_context(self):
        settings_obj = SystemSettings.get_settings()
        if settings_obj:
            currency_code = settings_obj.currency or getattr(settings, "DEFAULT_CURRENCY", "USD")
            return currency_code, settings_obj.currency_symbol or CURRENCY_SYMBOLS.get(currency_code, currency_code)
        currency_code = getattr(settings, "DEFAULT_CURRENCY", "USD")
        return currency_code, CURRENCY_SYMBOLS.get(currency_code, currency_code)

    def _allowed_commodity_values_for_category(self, cargo_category):
        if not cargo_category:
            return [value for value, _label in Order.CommodityType.choices]
        category_name = getattr(cargo_category, "name", str(cargo_category)).strip().lower()
        return self.CATEGORY_COMMODITY_MAP.get(category_name, [value for value, _label in Order.CommodityType.choices])

    def _set_commodity_choices(self):
        cargo_category = None
        if self.is_bound:
            cargo_category_id = self.data.get("cargo_category")
            if cargo_category_id:
                cargo_category = CargoCategory.objects.filter(pk=cargo_category_id).first()
        elif self.instance and self.instance.pk:
            cargo_category = self.instance.cargo_category
        else:
            cargo_category = self.initial.get("cargo_category")

        allowed_values = set(self._allowed_commodity_values_for_category(cargo_category))
        self.fields["commodity_type"].choices = [
            (value, label) for value, label in Order.CommodityType.choices if value in allowed_values
        ]
    
    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get('requested_pickup_date')
        delivery_date = cleaned_data.get('requested_delivery_date')
        cargo_category = cleaned_data.get("cargo_category")
        commodity_type = cleaned_data.get("commodity_type")
        fragile_items = cleaned_data.get("fragile_items")
        total_quantity = cleaned_data.get("total_quantity")
        unit = cleaned_data.get("unit")
        weight_kg = cleaned_data.get("weight_kg")
        
        # Validate dates
        if pickup_date and delivery_date:
            if pickup_date >= delivery_date:
                raise forms.ValidationError("Delivery date must be after pickup date")
            
            if pickup_date < timezone.now():
                raise forms.ValidationError("Pickup date cannot be in the past")
        
        allowed_values = self._allowed_commodity_values_for_category(cargo_category)
        if commodity_type and commodity_type not in allowed_values:
            self.add_error("commodity_type", "Selected commodity type does not match the chosen cargo category.")

        if total_quantity is not None and total_quantity <= 0:
            self.add_error("total_quantity", "Total quantity must be greater than zero.")
        if not unit:
            self.add_error("unit", "Unit must be selected.")

        if weight_kg is None or weight_kg <= 0:
            self.add_error("weight_kg", "Weight must be greater than zero.")

        if fragile_items:
            cleaned_data["requires_special_handling"] = True
        
        return cleaned_data


class OrderApprovalForm(forms.ModelForm):
    """Form for approving or rejecting orders"""
    
    action = forms.ChoiceField(
        choices=[
            ('approve', 'Approve'),
            ('reject', 'Reject'),
            ('request_changes', 'Request Changes')
        ],
        widget=forms.RadioSelect(attrs={
            'class': 'focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300'
        })
    )
    
    notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'rows': 4,
            'placeholder': 'Add notes for this approval decision...'
        }),
        required=False
    )
    
    class Meta:
        model = Order
        fields = ['action', 'notes']


class OrderAssignmentForm(forms.Form):
    """Form for assigning orders to vehicles and drivers"""
    
    vehicle = forms.ModelChoiceField(
        queryset=Vehicle.objects.filter(status='available'),
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    driver = forms.ModelChoiceField(
        queryset=Driver.objects.filter(status=Driver.DriverStatus.AVAILABLE),
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    estimated_departure = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'type': 'datetime-local'
        })
    )
    
    assignment_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'rows': 3,
            'placeholder': 'Notes for this assignment...'
        }),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set minimum departure time to now
        min_time = timezone.now()
        self.fields['estimated_departure'].widget.attrs['min'] = min_time.strftime('%Y-%m-%dT%H:%M')


class OrderNoteForm(forms.ModelForm):
    """Form for adding notes to orders"""
    
    class Meta:
        model = OrderNote
        fields = ['note', 'is_internal']
        
        widgets = {
            'note': forms.Textarea(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 4,
                'placeholder': 'Add a note...'
            }),
            'is_internal': forms.CheckboxInput(attrs={
                'class': 'focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300 rounded'
            })
        }


class OrderDocumentForm(forms.ModelForm):
    """Form for uploading documents to orders"""
    
    class Meta:
        model = OrderDocument
        fields = ['name', 'document_type', 'file']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Document name'
            }),
            'document_type': forms.Select(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
            })
        }


class OrderFilterForm(forms.Form):
    """Form for filtering orders in list view"""
    
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        required=False,
        empty_label="All Customers",
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Order.Status.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    commodity_type = forms.ChoiceField(
        choices=[('', 'All Commodities')] + Order.CommodityType.choices,
        required=False,
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    priority_level = forms.ChoiceField(
        choices=[('', 'All Priorities'), ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')],
        required=False,
        widget=forms.Select(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'type': 'date'
        })
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'Search by order number, customer, or description...'
        })
    )
