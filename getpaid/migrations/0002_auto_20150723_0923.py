# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('getpaid', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='payment',
            name='status',
            field=models.CharField(max_length=20, verbose_name='status', default='new', db_index=True, choices=[('new', 'new'), ('in_progress', 'in progress'), ('accepted_for_proc', 'accepted for processing'), ('partially_paid', 'partially paid'), ('paid', 'paid'), ('cancelled', 'cancelled'), ('failed', 'failed')]),
        ),
    ]
