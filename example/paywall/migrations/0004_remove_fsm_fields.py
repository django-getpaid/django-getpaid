"""Replace FSMField with CharField for paywall app."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('paywall', '0003_auto_20200419_1500'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymententry',
            name='payment_status',
            field=models.CharField(
                choices=[
                    ('new', 'new'),
                    ('prepared', 'in progress'),
                    ('pre-auth', 'pre-authed'),
                    ('charge_started', 'charge process started'),
                    ('partially_paid', 'partially paid'),
                    ('paid', 'paid'),
                    ('failed', 'failed'),
                    ('refund_started', 'refund started'),
                    ('refunded', 'refunded'),
                ],
                default='prepared',
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name='paymententry',
            name='fraud_status',
            field=models.CharField(
                choices=[
                    ('unknown', 'unknown'),
                    ('accepted', 'accepted'),
                    ('rejected', 'rejected'),
                    ('check', 'needs manual verification'),
                ],
                default='unknown',
                max_length=50,
            ),
        ),
    ]
