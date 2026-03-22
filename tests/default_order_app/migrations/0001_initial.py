from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Order',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'description',
                    models.CharField(default='Test order', max_length=100),
                ),
                (
                    'total',
                    models.DecimalField(
                        decimal_places=2,
                        default='10.00',
                        max_digits=8,
                    ),
                ),
                ('currency', models.CharField(default='EUR', max_length=3)),
            ],
            options={'abstract': False},
        ),
    ]
