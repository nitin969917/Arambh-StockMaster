from django import forms
from django.contrib.auth import get_user_model

from .models import Location, Product, StockDocument, StockMoveLine, Warehouse

User = get_user_model()


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "category", "unit_of_measure", "initial_stock", "low_stock_alert", "is_active"]


class WarehouseForm(forms.ModelForm):
    # User creation fields for warehouse
    user_username = forms.CharField(
        label="Warehouse Staff Login ID",
        max_length=150,
        help_text="6-12 characters, unique identifier for warehouse staff",
        required=True
    )
    user_email = forms.EmailField(
        label="Warehouse Staff Email",
        required=True,
        help_text="Email address for the warehouse staff account"
    )
    user_password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        required=True,
        help_text="Must be longer than 8 characters and contain a lowercase, uppercase and special character"
    )
    user_password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
        required=True
    )
    
    class Meta:
        model = Warehouse
        fields = ["name", "code", "address"]
    
    def clean_user_username(self):
        username = self.cleaned_data.get("user_username")
        if username:
            if not (6 <= len(username) <= 12):
                raise forms.ValidationError("Login ID must be between 6 and 12 characters.")
            if User.objects.filter(username=username).exists():
                raise forms.ValidationError("This Login ID is already taken.")
        return username
    
    def clean_user_email(self):
        email = self.cleaned_data.get("user_email")
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("user_password1")
        password2 = cleaned_data.get("user_password2")
        
        if password1 and password2:
            if password1 != password2:
                raise forms.ValidationError({"user_password2": "Passwords do not match."})
            
            # Validate password strength
            import re
            if len(password1) <= 8:
                raise forms.ValidationError({"user_password1": "Password must be longer than 8 characters."})
            if not re.search(r"[a-z]", password1):
                raise forms.ValidationError({"user_password1": "Password must contain at least one lowercase letter."})
            if not re.search(r"[A-Z]", password1):
                raise forms.ValidationError({"user_password1": "Password must contain at least one uppercase letter."})
            if not re.search(r"[^A-Za-z0-9]", password1):
                raise forms.ValidationError({"user_password1": "Password must contain at least one special character."})
        
        return cleaned_data


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["warehouse", "name", "code", "is_default"]


class StockDocumentBaseForm(forms.ModelForm):
    class Meta:
        model = StockDocument
        fields = ["reference", "contact_name", "source_location", "destination_location", "scheduled_date"]
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter locations by warehouse for warehouse staff - strict filtering by ID
        if user and user.is_warehouse_staff() and user.warehouse:
            user_warehouse_id = user.warehouse.id
            # Only show locations from the user's warehouse - use ID for strict comparison
            user_locations = Location.objects.filter(warehouse_id=user_warehouse_id)
            if 'source_location' in self.fields:
                self.fields['source_location'].queryset = user_locations
                self.fields['source_location'].empty_label = None  # Prevent showing other warehouses
            if 'destination_location' in self.fields:
                self.fields['destination_location'].queryset = user_locations
                self.fields['destination_location'].empty_label = None  # Prevent showing other warehouses
        
        # Make scheduled_date a date input
        if 'scheduled_date' in self.fields:
            self.fields['scheduled_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})


class ReceiptForm(forms.ModelForm):
    """
    Form for Receipts (incoming from external vendor).
    Only destination_location is required (which warehouse location to receive into).
    Source is external vendor.
    """
    class Meta:
        model = StockDocument
        fields = ["reference", "contact_name", "delivery_address", "destination_location", "scheduled_date"]
        labels = {
            "contact_name": "Vendor/Supplier Name",
            "delivery_address": "Vendor Address",
            "destination_location": "Receive Into Location",
        }
        help_texts = {
            "destination_location": "Select the warehouse location where goods will be received",
            "contact_name": "Name of the vendor/supplier",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Remove source_location field since it's not applicable for receipts
        if 'source_location' in self.fields:
            del self.fields['source_location']
        
        # Filter destination_location by warehouse for warehouse staff
        if user and user.is_warehouse_staff() and user.warehouse:
            user_warehouse_id = user.warehouse.id
            user_locations = Location.objects.filter(warehouse_id=user_warehouse_id)
            if 'destination_location' in self.fields:
                self.fields['destination_location'].queryset = user_locations
                self.fields['destination_location'].empty_label = None
        
        # Make scheduled_date a date input
        if 'scheduled_date' in self.fields:
            self.fields['scheduled_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        # Reduce textarea height for delivery_address
        if 'delivery_address' in self.fields:
            self.fields['delivery_address'].widget = forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})


class DeliveryForm(forms.ModelForm):
    """
    Form for Deliveries (outgoing to external customer).
    Only source_location is required (which warehouse location to ship from).
    Destination is external customer.
    """
    class Meta:
        model = StockDocument
        fields = ["reference", "contact_name", "delivery_address", "source_location", "scheduled_date"]
        labels = {
            "contact_name": "Customer Name",
            "delivery_address": "Delivery Address",
            "source_location": "Ship From Location",
        }
        help_texts = {
            "source_location": "Select the warehouse location where goods will be shipped from",
            "contact_name": "Name of the customer",
            "delivery_address": "Customer delivery address",
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Remove destination_location field since it's external customer
        if 'destination_location' in self.fields:
            del self.fields['destination_location']
        
        # Filter source_location by warehouse for warehouse staff
        if user and user.is_warehouse_staff() and user.warehouse:
            user_warehouse_id = user.warehouse.id
            user_locations = Location.objects.filter(warehouse_id=user_warehouse_id)
            if 'source_location' in self.fields:
                self.fields['source_location'].queryset = user_locations
                self.fields['source_location'].empty_label = None
        
        # Make scheduled_date a date input
        if 'scheduled_date' in self.fields:
            self.fields['scheduled_date'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        # Reduce textarea height for delivery_address
        if 'delivery_address' in self.fields:
            self.fields['delivery_address'].widget = forms.Textarea(attrs={'rows': 2, 'class': 'form-control'})


class StockMoveLineForm(forms.ModelForm):
    class Meta:
        model = StockMoveLine
        fields = ["product", "quantity"]


StockMoveLineFormSet = forms.inlineformset_factory(
    StockDocument,
    StockMoveLine,
    form=StockMoveLineForm,
    extra=1,
    can_delete=True,
)



