# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
from django.db import models, migrations
import getpaid.abstract_mixin


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.GETPAID_ORDER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('amount', models.DecimalField(max_digits=20, decimal_places=4, verbose_name='amount')),
                ('currency', models.CharField(verbose_name='currency', max_length=3)),
                ('status', models.CharField(choices=[('new', 'new'), ('in_progress', 'in progress'), ('partially_paid', 'partially paid'), ('paid', 'paid'), ('failed', 'failed')], default='new', verbose_name='status', db_index=True, max_length=20)),
                ('backend', models.CharField(verbose_name='backend', max_length=50)),
                ('created_on', models.DateTimeField(db_index=True, auto_now_add=True, verbose_name='created on')),
                ('paid_on', models.DateTimeField(blank=True, default=None, verbose_name='paid on', db_index=True, null=True)),
                ('amount_paid', models.DecimalField(max_digits=20, default=0, decimal_places=4, verbose_name='amount paid')),
                ('external_id', models.CharField(blank=True, null=True, verbose_name='external id', max_length=64)),
                ('description', models.CharField(blank=True, null=True, verbose_name='description', max_length=128)),
                ('order', models.ForeignKey(related_name='payments', to=settings.GETPAID_ORDER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'Payments',
                'ordering': ('-created_on',),
                'verbose_name': 'Payment',
            },
            bases=(models.Model, getpaid.abstract_mixin.AbstractMixin),
        ),
    ]
