import inspect

from asgiref.sync import async_to_sync
from django.core.exceptions import ImproperlyConfigured
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from getpaid_core.enums import BackendMethod, PaymentEvent
from getpaid_core.fsm import apply_payment_update
from getpaid_core.processor import BaseProcessor as CoreBaseProcessor
from getpaid_core.types import PaymentUpdate

from getpaid.adapters import (
    adapt_callback_request,
    call_processor_verify_callback,
)
from getpaid.repository import DjangoPaymentRepository


def prepare_payment(payment, request=None, view=None, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    result = _call_processor_method(
        processor.prepare_transaction,
        request=request,
        view=view,
        **kwargs,
    )
    if isinstance(result, HttpResponse):
        return result
    apply_payment_update(
        payment,
        PaymentUpdate(
            payment_event=PaymentEvent.PREPARED,
            external_id=result.external_id,
            provider_data=result.provider_data,
        ),
    )
    _save_payment(payment)
    return build_payment_response(payment, result, request=request, view=view)


def handle_callback_request(payment, request, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    if _uses_semantic_callback_contract(processor):
        data, headers, raw_body = adapt_callback_request(request)
        if _uses_semantic_verify_contract(processor):
            _call_processor_method(
                processor.verify_callback,
                data,
                headers,
                raw_body=raw_body,
                **kwargs,
            )
        else:
            call_processor_verify_callback(processor, request)
        update = _call_processor_method(
            processor.handle_callback,
            data,
            headers,
            raw_body=raw_body,
            **kwargs,
        )
        if isinstance(update, HttpResponse):
            return update
        apply_payment_update(payment, update)
        _save_payment(payment)
        return HttpResponse(b'OK')

    call_processor_verify_callback(processor, request)
    return processor.handle_paywall_callback(request, **kwargs)


def fetch_payment_status(payment):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    return _call_processor_method(processor.fetch_payment_status)


def fetch_and_update_payment_status(payment):
    payment = _normalize_payment(payment)
    update = fetch_payment_status(payment)
    apply_payment_update(payment, update)
    _save_payment(payment)
    return payment


def charge_payment(payment, amount=None, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    result = _call_processor_method(processor.charge, amount=amount, **kwargs)
    if result.success:
        if result.async_call:
            update = PaymentUpdate(
                payment_event=PaymentEvent.CHARGE_REQUESTED,
                provider_data=result.provider_data,
            )
        else:
            update = PaymentUpdate(
                payment_event=PaymentEvent.PAYMENT_CAPTURED,
                paid_amount=payment.amount_paid + result.amount_charged,
                provider_data=result.provider_data,
            )
        apply_payment_update(payment, update)
        _save_payment(payment)
    return result


def release_payment_lock(payment, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    amount = _call_processor_method(processor.release_lock, **kwargs)
    apply_payment_update(
        payment,
        PaymentUpdate(payment_event=PaymentEvent.LOCK_RELEASED),
    )
    _save_payment(payment)
    return amount


def start_payment_refund(payment, amount=None, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    result = _call_processor_method(
        processor.start_refund,
        amount=amount,
        **kwargs,
    )
    apply_payment_update(
        payment,
        PaymentUpdate(
            payment_event=PaymentEvent.REFUND_REQUESTED,
            provider_data=result.provider_data,
        ),
    )
    _save_payment(payment)
    return result


def cancel_payment_refund(payment, **kwargs):
    payment = _normalize_payment(payment)
    processor = payment._get_processor()
    success = _call_processor_method(processor.cancel_refund, **kwargs)
    if success:
        apply_payment_update(
            payment,
            PaymentUpdate(payment_event=PaymentEvent.REFUND_CANCELLED),
        )
        _save_payment(payment)
    return success


def build_payment_response(payment, result, request=None, view=None):
    if result.method is BackendMethod.POST:
        processor = payment._get_processor()
        if not hasattr(processor, 'get_form') or not hasattr(
            processor,
            'get_template_names',
        ):
            raise ImproperlyConfigured(
                'POST-based payments require a Django-aware processor.'
            )
        form = processor.get_form(result.form_data or {})
        return TemplateResponse(
            request=request,
            template=processor.get_template_names(view=view),
            context={
                'form': form,
                'paywall_url': result.redirect_url or '#',
            },
        )
    redirect_url = (
        result.redirect_url
        or payment._get_processor().get_our_baseurl(
            request,
        )
    )
    return HttpResponseRedirect(redirect_url)


def _call_processor_method(method, *args, **kwargs):
    if inspect.iscoroutinefunction(method):
        return async_to_sync(method)(*args, **kwargs)
    return method(*args, **kwargs)


def _save_payment(payment):
    repository = DjangoPaymentRepository(type(payment))
    return repository._save(payment)


def _normalize_payment(payment):
    repository = DjangoPaymentRepository(type(payment))
    return repository._normalize_payment(payment)


def _uses_semantic_callback_contract(processor):
    handle_method = getattr(processor, 'handle_callback', None)
    if handle_method is None:
        return False
    type_handle_method = getattr(type(processor), 'handle_callback', None)
    if type_handle_method is None:
        return inspect.iscoroutinefunction(handle_method)
    return type_handle_method is not CoreBaseProcessor.handle_callback


def _uses_semantic_verify_contract(processor):
    verify_method = getattr(processor, 'verify_callback', None)
    if verify_method is None:
        return False
    return inspect.iscoroutinefunction(verify_method)
