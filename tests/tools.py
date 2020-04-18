from getpaid.processor import BaseProcessor


class Plugin(BaseProcessor):
    display_name = "Test plugin"
    accepted_currencies = ["EUR", "USD"]
    slug = "test_plugin"

    def prepare_transaction(self, *args, **kwargs):
        return ""
