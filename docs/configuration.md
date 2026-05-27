# Configuration

## Core Settings

### `GETPAID_ORDER_MODEL`

**Required.** No default.

The model to represent an Order. Must implement the methods defined in
`AbstractOrder` (or the `Order` protocol from getpaid-core).

```python
GETPAID_ORDER_MODEL = "yourapp.Order"
```

```{warning}
You cannot change `GETPAID_ORDER_MODEL` after creating and running migrations
that depend on it. Set it at project start.
```

### `GETPAID_PAYMENT_MODEL`

**Default:** `"getpaid.Payment"`

The model to represent a Payment. Override to use a custom Payment model.
See {doc}`customization`.

```{warning}
You cannot change `GETPAID_PAYMENT_MODEL` after creating and running
migrations that depend on it. Set it at project start.
```

## Backend Settings

Configure payment backends in `GETPAID_BACKEND_SETTINGS`. Backend settings
accept either the backend slug or the legacy dotted module path as the key.
Prefer the slug for new projects:

```python
GETPAID_BACKEND_SETTINGS = {
    "dummy": {
        "confirmation_method": "push",
        "gateway": reverse_lazy("paywall:gateway"),
        "callback_ip_allowlist": ["203.0.113.10", "203.0.113.0/24"],
    },
    "getpaid_payu": {
        "pos_id": 12345,
        "second_key": "your_key_here",
        "oauth_id": 12345,
        "oauth_secret": "your_secret_here",
    },
}
```

Each backend defines its own settings — check the backend's documentation.

### `callback_ip_allowlist`

**Default:** not set

Optional per-backend list of source IPs or CIDR ranges allowed to call the
callback endpoint for that backend.

```python
GETPAID_BACKEND_SETTINGS = {
    "paynow": {
        "api_key": "your-api-key",
        "signature_key": "your-signature-key",
        "callback_ip_allowlist": [
            "203.0.113.10",
            "203.0.113.0/24",
        ],
    },
}
```

Notes:

- The allowlist is checked before the callback is processed.
- If the callback source IP is outside the allowlist, the callback is rejected
  with HTTP 403.
- IP allowlisting is a secondary control. Backends should still implement
  `verify_callback()` and validate gateway signatures.

## Optional Settings

Optional settings live in the `GETPAID` dictionary (empty by default):

```python
GETPAID = {
    "POST_TEMPLATE": "my_post_form.html",
    "HIDE_LONELY_PLUGIN": True,
    "CALLBACK_SOURCE_IP_HEADER": "X-Forwarded-For",
    "CALLBACK_TRUSTED_PROXIES": ["10.0.0.0/8"],
}
```

### `POST_TEMPLATE`

**Default:** `None`

Override the template used to render POST-method payment forms.
Can also be set per-backend in `GETPAID_BACKEND_SETTINGS`.

### `POST_FORM_CLASS`

**Default:** `None`

Override the form class for POST-method payment flows.
Use a full dotted path. Can also be set per-backend.

### `SUCCESS_URL`

**Default:** `None`

Custom view name for successful returns from the payment gateway.
Can also be set per-backend. When not set, redirects to the Order's
`get_return_url()`.

### `FAILURE_URL`

**Default:** `None`

Custom view name for failed returns from the payment gateway.
Can also be set per-backend.

### `HIDE_LONELY_PLUGIN`

**Default:** `False`

When `True`, hides the plugin selection widget if only one plugin is
available, using it as the default automatically.

### `VALIDATORS`

**Default:** `[]`

Import paths for validators run against a payment before it is sent to
the gateway. Can also be set per-backend.

### `CALLBACK_SOURCE_IP_HEADER`

**Default:** `None`

Optional HTTP header name used to extract the original client IP for callback
IP allowlist checks when django-getpaid is behind a trusted reverse proxy.

Example values:

- `"X-Forwarded-For"`
- `"CF-Connecting-IP"`

Behavior:

- If this setting is not configured, django-getpaid uses `REMOTE_ADDR`.
- If this setting is configured, the header is trusted only when
  `REMOTE_ADDR` belongs to `CALLBACK_TRUSTED_PROXIES`.
- For comma-separated headers such as `X-Forwarded-For`, django-getpaid walks
  the proxy chain from right to left and uses the first address that is not a
  trusted proxy.
- If a trusted proxy request omits the configured header, the callback is
  rejected with HTTP 403.

### `CALLBACK_TRUSTED_PROXIES`

**Default:** `[]`

List of trusted reverse-proxy IPs or CIDR ranges allowed to supply the
`CALLBACK_SOURCE_IP_HEADER` value.

```python
GETPAID = {
    "CALLBACK_SOURCE_IP_HEADER": "X-Forwarded-For",
    "CALLBACK_TRUSTED_PROXIES": [
        "10.0.0.0/8",
        "192.168.0.0/16",
    ],
}
```

Notes:

- This setting is ignored unless `CALLBACK_SOURCE_IP_HEADER` is set.
- Do not trust forwarded client IP headers from arbitrary peers. The header is
  spoofable unless the immediate peer is a trusted proxy under your control.
- If you configure `CALLBACK_SOURCE_IP_HEADER`, you should also enforce
  provider IP filtering at the reverse proxy or load balancer.
