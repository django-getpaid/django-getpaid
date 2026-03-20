from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0005_remove_fsm_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='custompayment',
            name='provider_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='provider data',
            ),
        ),
    ]
