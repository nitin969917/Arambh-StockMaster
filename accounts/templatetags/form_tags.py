from django import template

register = template.Library()


@register.filter(name="add_class")
def add_class(field, css_class):
    """
    Simple helper to append a CSS class to a form field widget in templates.
    Usage: {{ form.field|add_class:"form-control" }}
    """
    return field.as_widget(attrs={**field.field.widget.attrs, "class": css_class})



