from django.urls.converters import StringConverter


class CurrencyConverter(StringConverter):
    regex = "[A-Z]{3}"
