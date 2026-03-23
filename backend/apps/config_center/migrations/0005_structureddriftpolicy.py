from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('config_center', '0004_configcompliance_intent'),
    ]

    operations = [
        migrations.CreateModel(
            name='StructuredDriftPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='default', max_length=100, verbose_name='策略名称')),
                ('version', models.CharField(default='v1', max_length=100, verbose_name='版本标识')),
                ('policy_content', models.JSONField(blank=True, default=dict, verbose_name='策略内容')),
                ('is_active', models.BooleanField(default=False, verbose_name='是否激活')),
                ('remark', models.TextField(blank=True, default='', verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '结构化漂移策略表',
                'verbose_name_plural': '结构化漂移策略表',
                'db_table': 'structured_drift_policy',
            },
        ),
        migrations.AddIndex(
            model_name='structureddriftpolicy',
            index=models.Index(fields=['is_active'], name='structured__is_acti_3d559e_idx'),
        ),
        migrations.AddIndex(
            model_name='structureddriftpolicy',
            index=models.Index(fields=['name', 'updated_at'], name='structured__name_a23e5f_idx'),
        ),
    ]
