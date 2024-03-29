# Generated by Django 3.2.19 on 2023-06-27 02:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('asset', '0003_alter_adminrecord_admin_login_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_server', to='asset.assetaccount', verbose_name='账户')),
                ('server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_account', to='asset.server', verbose_name='服务器')),
            ],
            options={
                'verbose_name_plural': '服务器和账户关联表',
                'db_table': 'asset_account2server',
                'unique_together': {('server', 'account')},
            },
        ),
    ]
