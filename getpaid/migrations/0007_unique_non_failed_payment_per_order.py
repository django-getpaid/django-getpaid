# Generated migration for DJANGO-002: unique non-failed payment per order constraint.

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ('getpaid', '0006_payment_unique_external_id'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='payment',
            constraint=models.UniqueConstraint(
                fields=('order',),
                condition=~Q(status='failed'),
                name='getpaid_unique_non_failed_payment_per_order',
            ),
        ),
    ]
