from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dcs_control', '0001_add_block_and_dnat_record_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='FirewallPolicyAuditRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audit_type', models.CharField(choices=[('sec_policy', '安全策略审计')], default='sec_policy', max_length=32, verbose_name='审计类型')),
                ('vendor', models.CharField(max_length=20, verbose_name='厂商')),
                ('device_ip', models.GenericIPAddressField(protocol='both', unpack_ipv4=True, verbose_name='设备管理IP')),
                ('operator', models.CharField(blank=True, default='', max_length=64, verbose_name='操作人')),
                ('source', models.CharField(blank=True, default='NetClaw-CN', max_length=64, verbose_name='来源系统')),
                ('status', models.CharField(choices=[('success', '成功'), ('partial', '部分成功'), ('failed', '失败')], default='success', max_length=16, verbose_name='执行状态')),
                ('summary', models.JSONField(default=dict, verbose_name='摘要信息')),
                ('findings', models.JSONField(default=list, verbose_name='风险发现')),
                ('audit_payload', models.JSONField(default=dict, verbose_name='完整审计载荷')),
                ('auto_flow_id', models.IntegerField(blank=True, null=True, verbose_name='关联 AutoFlow ID')),
                ('task_id', models.CharField(blank=True, default='', max_length=128, verbose_name='关联任务ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '防火墙审计记录',
                'verbose_name_plural': '防火墙审计记录',
                'db_table': 'dcs_firewall_policy_audit_record',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='firewallpolicyauditrecord',
            index=models.Index(fields=['device_ip', 'created_at'], name='idx_fw_audit_device_time'),
        ),
        migrations.AddIndex(
            model_name='firewallpolicyauditrecord',
            index=models.Index(fields=['vendor', 'created_at'], name='idx_fw_audit_vendor_time'),
        ),
        migrations.AddIndex(
            model_name='firewallpolicyauditrecord',
            index=models.Index(fields=['status'], name='idx_fw_audit_status'),
        ),
        migrations.AddIndex(
            model_name='firewallpolicyauditrecord',
            index=models.Index(fields=['auto_flow_id'], name='idx_fw_audit_flow'),
        ),
    ]
