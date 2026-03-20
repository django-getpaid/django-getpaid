from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('getpaid', '0003_remove_fsm_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='provider_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='provider data',
            ),
        ),
    ]
