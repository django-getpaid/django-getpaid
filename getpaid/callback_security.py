"""Callback security checks for payment provider webhooks."""

from __future__ import annotations

from ipaddress import ip_address, ip_network
from typing import Any

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from getpaid_core.processor import BaseProcessor as CoreBaseProcessor

from getpaid.exceptions import InvalidCallbackError
from getpaid.processor import BaseProcessor as DjangoBaseProcessor


def enforce_callback_security(processor: Any, request: Any) -> None:
    """Validate provider callback security before processing the payload."""
    _enforce_signed_backend_in_production(processor)
    _enforce_ip_allowlist(processor, request)


def has_custom_callback_verification(processor: Any) -> bool:
    """Return True when the processor implements real callback verification."""
    verify_method = getattr(processor, 'verify_callback', None)
    if verify_method is None:
        return False

    type_verify_method = getattr(type(processor), 'verify_callback', None)
    if type_verify_method is None:
        return True

    return type_verify_method not in {
        DjangoBaseProcessor.verify_callback,
        CoreBaseProcessor.verify_callback,
    }


def _enforce_signed_backend_in_production(processor: Any) -> None:
    if django_settings.DEBUG:
        return
    if has_custom_callback_verification(processor):
        return
    raise InvalidCallbackError(
        'Unsigned callback backends are not allowed when DEBUG is False.'
    )


def _enforce_ip_allowlist(processor: Any, request: Any) -> None:
    allowlist = _get_callback_ip_allowlist(processor)
    if not allowlist:
        return

    client_ip = ip_address(get_callback_request_ip(request))
    networks = [ip_network(entry, strict=False) for entry in allowlist]
    if any(client_ip in network for network in networks):
        return

    raise InvalidCallbackError(
        f'Callback request from IP {str(client_ip)!r} is not allowed.'
    )


def get_callback_request_ip(request: Any) -> str:
    """Return the client IP used for callback allowlist checks."""
    remote_addr = request.META.get('REMOTE_ADDR', '')
    if not remote_addr:
        raise InvalidCallbackError(
            'Callback request has no REMOTE_ADDR for IP allowlist checks.'
        )

    source_header = _get_global_callback_setting(
        'CALLBACK_SOURCE_IP_HEADER',
        None,
    )
    if not source_header:
        return remote_addr

    trusted_proxies = _get_global_callback_setting(
        'CALLBACK_TRUSTED_PROXIES',
        [],
    )
    if not trusted_proxies:
        raise ImproperlyConfigured(
            'GETPAID["CALLBACK_SOURCE_IP_HEADER"] requires '
            'GETPAID["CALLBACK_TRUSTED_PROXIES"].'
        )

    trusted_networks = [
        ip_network(entry, strict=False) for entry in trusted_proxies
    ]
    peer_ip = ip_address(remote_addr)
    if not any(peer_ip in network for network in trusted_networks):
        return remote_addr

    forwarded_value = _get_request_header_value(request, str(source_header))
    if not forwarded_value:
        raise InvalidCallbackError(
            'Trusted proxy callback request is missing the configured '
            'source IP header.'
        )

    forwarded_chain = [
        entry.strip() for entry in forwarded_value.split(',') if entry.strip()
    ]
    if not forwarded_chain:
        raise InvalidCallbackError(
            'Configured callback source IP header is empty.'
        )

    for entry in reversed([*forwarded_chain, remote_addr]):
        try:
            candidate_ip = ip_address(entry)
        except ValueError as exc:
            raise InvalidCallbackError(
                f'Invalid callback IP address value {entry!r}.'
            ) from exc
        if any(candidate_ip in network for network in trusted_networks):
            continue
        return str(candidate_ip)

    raise InvalidCallbackError(
        'Callback IP header did not contain an untrusted client address.'
    )


def _get_callback_ip_allowlist(processor: Any) -> list[str]:
    getter = getattr(processor, 'get_setting', None)
    if not callable(getter):
        return []

    configured = getter('callback_ip_allowlist', None)
    if configured is None:
        return []
    if isinstance(configured, str):
        return [configured]
    return list(configured)


def _get_global_callback_setting(name: str, default: Any) -> Any:
    return getattr(django_settings, 'GETPAID', {}).get(name, default)


def _get_request_header_value(request: Any, header_name: str) -> str:
    value = request.headers.get(header_name, '')
    if value:
        return value

    direct_meta = request.META.get(header_name, '')
    if direct_meta:
        return direct_meta

    normalized_meta = f'HTTP_{header_name.upper().replace("-", "_")}'
    return request.META.get(normalized_meta, '')
