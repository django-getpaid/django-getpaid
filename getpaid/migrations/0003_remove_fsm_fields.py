"""Replace FSMField with CharField.

FSMField is a CharField subclass, so the database column is already
a varchar. This migration updates Django's field tracking only --
no actual database changes occur.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('getpaid', '0002_auto_20200417_2107'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
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
                db_index=True,
                default='new',
                max_length=50,
                verbose_name='status',
            ),
        ),
        migrations.AlterField(
            model_name='payment',
            name='fraud_status',
            field=models.CharField(
                choices=[
                    ('unknown', 'unknown'),
                    ('accepted', 'accepted'),
                    ('rejected', 'rejected'),
                    ('check', 'needs manual verification'),
                ],
                db_index=True,
                default='unknown',
                max_length=20,
                verbose_name='fraud status',
            ),
        ),
    ]
