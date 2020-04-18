import os

import swapper
from django.test import LiveServerTestCase, RequestFactory

from getpaid.registry import registry

from .tools import Plugin

dummy = "getpaid.backends.dummy"

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")


class TestModels(LiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        os.environ["_PAYWALL_URL"] = cls.live_server_url
        registry.register(Plugin)
        cls.factory = RequestFactory()
