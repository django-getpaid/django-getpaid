from getpaid.processor import BaseProcessor


class Plugin(BaseProcessor):
    display_name = "Test plugin"
    accepted_currencies = ["EUR", "USD"]
    slug = "test_plugin"

    def get_paywall_url(self, *args, **kwargs):
        return "test"

    def get_paywall_params(self, *args, **kwargs):
        return {}
