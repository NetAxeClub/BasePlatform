from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('config_center', '0005_structureddriftpolicy'),
    ]

    operations = [
        migrations.CreateModel(
            name='StructuredDriftPolicyAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('CREATE', 'CREATE'), ('UPDATE', 'UPDATE'), ('ACTIVATE', 'ACTIVATE'), ('ROLLBACK', 'ROLLBACK'), ('DELETE', 'DELETE')], default='UPDATE', max_length=30, verbose_name='动作')),
                ('actor', models.CharField(blank=True, default='', max_length=150, verbose_name='执行人')),
                ('note', models.TextField(blank=True, default='', verbose_name='备注')),
                ('effective_policy_before', models.JSONField(blank=True, default=dict, verbose_name='变更前生效策略')),
                ('effective_policy_after', models.JSONField(blank=True, default=dict, verbose_name='变更后生效策略')),
                ('effective_policy_diff', models.JSONField(blank=True, default=dict, verbose_name='生效策略差异摘要')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('policy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='audit_logs', to='config_center.structureddriftpolicy', verbose_name='目标策略')),
                ('previous_policy', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='superseded_audit_logs', to='config_center.structureddriftpolicy', verbose_name='前一激活策略')),
            ],
            options={
                'verbose_name': '结构化漂移策略审计表',
                'verbose_name_plural': '结构化漂移策略审计表',
                'db_table': 'structured_drift_policy_audit',
            },
        ),
        migrations.AddIndex(
            model_name='structureddriftpolicyaudit',
            index=models.Index(fields=['action', 'created_at'], name='structured__action__1f25d0_idx'),
        ),
        migrations.AddIndex(
            model_name='structureddriftpolicyaudit',
            index=models.Index(fields=['policy', 'created_at'], name='structured__policy__043778_idx'),
        ),
    ]
