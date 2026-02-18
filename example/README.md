## Example Project for django-getpaid

This example demonstrates comprehensive payment processing with multiple backends, error handling, and admin integration.

### Features

- **Multiple payment backends**: DummyProcessor (for testing), PayU, and Paynow
- **Order creation flow**: Simple order form → payment method selection → paywall → callback → success/failure
- **Error handling**: Graceful error pages for failed payments, expired sessions, invalid callbacks
- **Admin integration**: Manage orders and payments via Django admin
- **Sandbox mode**: Pre-configured with sandbox keys for testing (no real payments)

### Quick Start

1. Navigate to the `example` directory
2. Install dependencies:

		uv sync

3. Apply migrations:

		uv run python manage.py migrate

4. Create admin user (optional):

		uv run python manage.py createsuperuser

5. Run the development server:

		uv run python manage.py runserver

6. Access the application:
   - **Main app**: `http://127.0.0.1:8000`
   - **Admin panel**: `http://127.0.0.1:8000/admin`

### Payment Backends Configuration

The example is pre-configured with sandbox credentials for all backends. By default, all backends are available for testing.

#### Environment Variables (Optional)

You can override sandbox keys with environment variables:

**DummyProcessor (testing backend)**:
```bash
export DUMMY_POS_ID=12345
export DUMMY_SECOND_KEY=91ae651578c5b5aa93f2d38a9be8ce11
export DUMMY_CLIENT_ID=12345
export DUMMY_CLIENT_SECRET=12f071174cb7eb79d4aac5bc2f07563f
```

**PayU (PLN sandbox)**:
```bash
export PAYU_POS_ID=300746
export PAYU_SECOND_KEY=b6ca15b0d1020e8094d9b5f8d163db54
export PAYU_OAUTH_ID=300746
export PAYU_OAUTH_SECRET=2ee86a66e5d97e3fadc400c9f19b065d
```

**Paynow (sandbox)**:
```bash
export PAYNOW_API_KEY=d2e1d881-40b0-4b7e-9168-181bae3dc4e0
export PAYNOW_SIGN_KEY=8e42a868-5562-440d-817c-4921632fb049
```

### Usage

1. **Create an order**: Fill out the order form on the home page
2. **Select payment method**: Choose from available backends (DummyProcessor, PayU, Paynow)
3. **Complete payment**: Use the paywall simulator to test payment flows
4. **View results**: Check order status and payment details

### Admin Panel

Access the admin panel at `/admin` to:
- View all orders and their statuses
- Inspect payment details (amount, status, backend, timestamps)
- Search orders and payments by ID
- Monitor payment lifecycle

### Testing Payment Flows

**DummyProcessor** provides instant testing:
- Success: Complete payment immediately via paywall
- Failure: Simulate payment failures
- No external services required

**PayU and Paynow** backends are configured with sandbox credentials:
- All transactions use sandbox mode (no real money)
- Test various payment scenarios
- Callbacks are handled automatically

### Troubleshooting

**Migrations fail**: Ensure you're in the `example` directory and run `uv run python manage.py migrate`

**Admin not accessible**: Create a superuser with `uv run python manage.py createsuperuser`

**Payment backend errors**: Check that sandbox credentials are correctly configured in `example/settings.py`
