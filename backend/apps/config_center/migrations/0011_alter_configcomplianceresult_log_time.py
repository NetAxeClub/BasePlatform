# Generated by Django 3.2.23 on 2024-10-12 07:56

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('config_center', '0010_auto_20241012_1537'),
    ]

    operations = [
        migrations.AlterField(
            model_name='configcomplianceresult',
            name='log_time',
            field=models.DateTimeField(default=datetime.datetime(2024, 10, 12, 7, 56, 8, 185882, tzinfo=utc), verbose_name='检查时间'),
        ),
    ]
