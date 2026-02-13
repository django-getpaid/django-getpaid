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

Configure payment backends in `GETPAID_BACKEND_SETTINGS`. Use the plugin's
dotted import path as the key:

```python
GETPAID_BACKEND_SETTINGS = {
    "getpaid.backends.dummy": {
        "confirmation_method": "push",
        "gateway": reverse_lazy("paywall:gateway"),
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

## Optional Settings

Optional settings live in the `GETPAID` dictionary (empty by default):

```python
GETPAID = {
    "POST_TEMPLATE": "my_post_form.html",
    "HIDE_LONELY_PLUGIN": True,
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
