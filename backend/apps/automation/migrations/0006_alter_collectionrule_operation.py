# Generated by Django 3.2.19 on 2023-07-13 01:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('automation', '0005_collectionmatchrule_value'),
    ]

    operations = [
        migrations.AlterField(
            model_name='collectionrule',
            name='operation',
            field=models.CharField(blank=True, default='', max_length=50, null=True, verbose_name='运算符'),
        ),
    ]
