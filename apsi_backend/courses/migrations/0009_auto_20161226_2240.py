# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2016-12-26 22:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0008_auto_20161226_2236'),
    ]

    operations = [
        migrations.AlterField(
            model_name='timeslot',
            name='day',
            field=models.IntegerField(choices=[(0, 'Poniedziałek'), (1, 'Wtorek'), (2, 'Środa'), (3, 'Czwartek'), (4, 'Piątek')]),
        ),
    ]
