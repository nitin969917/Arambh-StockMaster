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



