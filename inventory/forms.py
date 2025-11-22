from django import forms

from .models import Location, Product, StockDocument, StockMoveLine, Warehouse


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "category", "unit_of_measure", "initial_stock", "is_active"]


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "code", "address"]


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ["warehouse", "name", "code", "is_default"]


class StockDocumentBaseForm(forms.ModelForm):
    class Meta:
        model = StockDocument
        fields = ["reference", "contact_name", "source_location", "destination_location", "scheduled_date"]


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
        super().__init__(*args, **kwargs)
        # Remove source_location field since it's not applicable for receipts
        if 'source_location' in self.fields:
            del self.fields['source_location']


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
        super().__init__(*args, **kwargs)
        # Remove destination_location field since it's external customer
        if 'destination_location' in self.fields:
            del self.fields['destination_location']


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



