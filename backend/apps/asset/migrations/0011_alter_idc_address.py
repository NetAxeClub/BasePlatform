# Generated by Django 3.2.19 on 2023-11-27 07:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asset', '0010_auto_20231123_1052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='idc',
            name='address',
            field=models.CharField(default='', max_length=100, null=True, verbose_name='机房地址'),
        ),
    ]
