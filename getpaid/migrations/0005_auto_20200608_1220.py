# Generated by Django 3.0.6 on 2020-06-08 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('getpaid', '0004_auto_20200529_1019'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='description',
            field=models.CharField(blank=True, default='', max_length=256, verbose_name='description'),
        ),
    ]
