class BaseProcessor(object):
    display_name = None
    accepted_currencies = None
    logo_url = None
    slug = None  # for friendly urls

    def __init__(self, payment):
        self.payment = payment

    def get_form(self, post_data):
        """
        Only used if the payment processor requires POST requests.
        Generates a form only containg hidden input fields.
        """
        from getpaid.forms import PaymentHiddenInputsPostForm
        return PaymentHiddenInputsPostForm(items=post_data)

    def handle_callback(self, request, *args, **kwargs):
        """
        This method handles the callback from payment broker for the purpose
        of updating the payment status in our system.
        :param args:
        :param kwargs:
        :return: HttpResponse instance
        """
        raise NotImplementedError

    @classmethod
    def get_display_name(cls):
        return cls.display_name

    @classmethod
    def get_accepted_currencies(cls):
        return cls.accepted_currencies

    @classmethod
    def get_logo_url(cls):
        return cls.logo_url
