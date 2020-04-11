from getpaid.processor import BaseProcessor


class Plugin(BaseProcessor):
    display_name = "Test plugin"
    accepted_currencies = ["EUR", "USD"]
    slug = "test_plugin"

    def process_payment(self, *args, **kwargs):
        return ""
