# Generated by Django 3.2.19 on 2023-06-01 16:18

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='InterfaceUsed',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('host', models.CharField(blank=True, max_length=200, null=True, verbose_name='主机名')),
                ('host_id', models.CharField(blank=True, max_length=50, null=True, verbose_name='硬件ID')),
                ('host_ip', models.GenericIPAddressField(blank=True, null=True, verbose_name='管理IP')),
                ('int_total', models.IntegerField(blank=True, null=True, verbose_name='总接口数')),
                ('int_used', models.IntegerField(blank=True, null=True, verbose_name='已使用')),
                ('int_unused', models.IntegerField(blank=True, null=True, verbose_name='未使用')),
                ('utilization', models.FloatField(blank=True, null=True, verbose_name='使用率')),
                ('int_used_1g', models.IntegerField(blank=True, null=True, verbose_name='1G接口使用')),
                ('int_used_10m', models.IntegerField(blank=True, null=True, verbose_name='10M接口使用')),
                ('int_used_100m', models.IntegerField(blank=True, null=True, verbose_name='100M接口使用')),
                ('int_used_10g', models.IntegerField(blank=True, null=True, verbose_name='10G接口使用')),
                ('int_used_20g', models.IntegerField(blank=True, null=True, verbose_name='20G接口使用')),
                ('int_used_25g', models.IntegerField(blank=True, null=True, verbose_name='25G接口使用')),
                ('int_used_40g', models.IntegerField(blank=True, null=True, verbose_name='40G接口使用')),
                ('int_used_100g', models.IntegerField(blank=True, null=True, verbose_name='100G接口使用')),
                ('int_used_200g', models.IntegerField(blank=True, null=True, verbose_name='200G接口使用')),
                ('int_used_400g', models.IntegerField(blank=True, null=True, verbose_name='400G接口使用')),
                ('int_used_irf', models.IntegerField(blank=True, null=True, verbose_name='堆叠接口使用')),
                ('int_used_auto', models.IntegerField(blank=True, null=True, verbose_name='auto接口使用')),
                ('int_unused_1g', models.IntegerField(blank=True, null=True, verbose_name='1G接口未使用')),
                ('int_unused_10m', models.IntegerField(blank=True, null=True, verbose_name='10M接口未使用')),
                ('int_unused_100m', models.IntegerField(blank=True, null=True, verbose_name='100M接口未使用')),
                ('int_unused_10g', models.IntegerField(blank=True, null=True, verbose_name='10G接口未使用')),
                ('int_unused_20g', models.IntegerField(blank=True, null=True, verbose_name='20G接口未使用')),
                ('int_unused_25g', models.IntegerField(blank=True, null=True, verbose_name='25G接口未使用')),
                ('int_unused_40g', models.IntegerField(blank=True, null=True, verbose_name='40G接口未使用')),
                ('int_unused_100g', models.IntegerField(blank=True, null=True, verbose_name='100G接口未使用')),
                ('int_unused_200g', models.IntegerField(blank=True, null=True, verbose_name='200G接口未使用')),
                ('int_unused_400g', models.IntegerField(blank=True, null=True, verbose_name='400G接口未使用')),
                ('int_unused_irf', models.IntegerField(blank=True, null=True, verbose_name='堆叠接口未使用')),
                ('int_unused_auto', models.IntegerField(blank=True, null=True, verbose_name='auto接口未使用')),
                ('log_time', models.DateTimeField(blank=True, null=True, verbose_name='记录时间')),
            ],
            options={
                'verbose_name_plural': '接口利用率表',
                'db_table': 'interface_used',
            },
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['host'], name='interface_u_host_11dccc_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['host_id'], name='interface_u_host_id_d77a93_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['host_ip'], name='interface_u_host_ip_60ab77_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_total'], name='interface_u_int_tot_c35bda_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used'], name='interface_u_int_use_7928d1_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused'], name='interface_u_int_unu_b48a08_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['utilization'], name='interface_u_utiliza_cff84a_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_1g'], name='interface_u_int_use_a6f132_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_10m'], name='interface_u_int_use_4f48aa_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_100m'], name='interface_u_int_use_8c2a44_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_10g'], name='interface_u_int_use_1362eb_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_20g'], name='interface_u_int_use_cb2752_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_25g'], name='interface_u_int_use_9a53a9_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_40g'], name='interface_u_int_use_e4d62c_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_100g'], name='interface_u_int_use_db4657_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_irf'], name='interface_u_int_use_771939_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_used_auto'], name='interface_u_int_use_cf2cff_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_1g'], name='interface_u_int_unu_22e0f3_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_10m'], name='interface_u_int_unu_fa2ddb_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_100m'], name='interface_u_int_unu_dbb757_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_10g'], name='interface_u_int_unu_9cde3e_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_20g'], name='interface_u_int_unu_0f4dc5_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_25g'], name='interface_u_int_unu_366e5c_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_40g'], name='interface_u_int_unu_e285ca_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_100g'], name='interface_u_int_unu_f4ad0d_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_irf'], name='interface_u_int_unu_b31f27_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['int_unused_auto'], name='interface_u_int_unu_2e47db_idx'),
        ),
        migrations.AddIndex(
            model_name='interfaceused',
            index=models.Index(fields=['log_time'], name='interface_u_log_tim_5b4cc1_idx'),
        ),
    ]
