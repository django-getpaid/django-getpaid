import logging

logger = logging.getLogger('getpaid_example')


def new_payment_query_listener(sender, order=None, payment=None, **kwargs):
    """
    Here we fill only two obligatory fields of payment, and leave signal handler
    """
    payment.amount = order.total
    payment.currency = order.currency

    logger.debug("new_payment_query_listener, amount=%s, currency=%s",
                 payment.amount, payment.currency)


def payment_status_changed_listener(sender, instance, old_status, new_status, **kwargs):
    """
    Here we will actually do something, when payment is accepted.
    E.g. lets change an order status.
    """
    logger.debug("payment_status_changed_listener, old=%s, new=%s", old_status,
                 new_status)
    if old_status != 'paid' and new_status == 'paid':
        # Ensures that we process order only one
        instance.order.status = 'P'
        instance.order.save()


def user_data_query_listener(sender, order=None, user_data=None, **kwargs):
    """
    Here we fill some static user data, just for test
    """
    user_data['email'] = 'test@test.com'
    # user_data['lang'] = 'EN'
