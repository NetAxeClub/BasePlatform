from django.db import models
from django.utils import timezone


class SupportVendor:
    CHOICES = (
        ('H3C', 'H3C'),
        ('HUAWEI', 'HUAWEI'),
        ('Cisco_ios', 'Cisco_ios'),
        ('Ruijie', 'Ruijie'),
        ('Hillstone', 'Hillstone'),
    )


class ConfigComplianceRule(models.Model):
    name = models.CharField(max_length=255, verbose_name="规则名", unique=True, null=False)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    class Meta:
        verbose_name = "配置合规规则表"
        verbose_name_plural = verbose_name
        db_table = 'config_compliance_rule'  # 通过db_table自定义数据表名

    def __str__(self):
        return self.name


# 配置合规表
class ConfigCompliance(models.Model):
    """配置合规"""
    CATEGORY_CHOICES = (
        ('switch', 'switch'),
        ('firewall', 'firewall'),
        ('router', 'router')
    )
    MATCH_CHOICES = (
        ('match-compliance', 'match-compliance'),  # 匹配-合规 反之 不匹配-不合规
        # ('match-non-compliance', 'match-non-compliance'),  # 匹配-不合规
        ('mismatch-compliance', 'mismatch-compliance'),  # 不匹配-合规 反之 匹配-不合规
        # ('mismatch-non-compliance', 'mismatch-non-compliance'),  # 不匹配-不合规
    )
    # name = models.CharField(verbose_name='名称', max_length=50, null=False, unique=True)
    vendor = models.CharField(verbose_name='厂商', choices=SupportVendor.CHOICES, max_length=50, default='H3C')
    # category = models.CharField(verbose_name='类型', choices=CATEGORY_CHOICES, max_length=50, default='交换机')
    pattern = models.CharField(verbose_name='模式', choices=MATCH_CHOICES, max_length=50, default='match-compliance')
    regex = models.TextField(verbose_name='表达式', null=False, default='', blank=False)
    intent = models.TextField(verbose_name='设计意图', null=False, default='', blank=True)
    # is_repair = models.BooleanField(verbose_name="是否修正", null=False, default=False, blank=False)
    # repair_cmds = models.TextField(verbose_name='修复命令', null=True, default='', blank=True)
    datetime = models.DateTimeField(auto_now=True, verbose_name='创建日期')
    rule = models.ForeignKey("ConfigComplianceRule", on_delete=models.CASCADE,
                             null=True, blank=True, related_name='relate_compliance')

    def __str__(self):
        return '%s-%s-%s' % (self.vendor, self.pattern, self.datetime)

    class Meta:
        verbose_name_plural = '配置合规表'
        verbose_name = '配置合规表'
        db_table = 'config_compliance'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['vendor', ]),
                   models.Index(fields=['datetime', ])]


# 配置模板表
class ConfigTemplate(models.Model):
    vendor = models.CharField(verbose_name="厂商", choices=SupportVendor.CHOICES, default='H3C', max_length=100)
    name = models.CharField(verbose_name='配置项名称', max_length=100, null=False, unique=True)
    config_yaml = models.TextField(verbose_name='yaml内容', null=False, blank=True, default='')
    config_jinja2 = models.TextField(verbose_name='jinja2内容', null=False, blank=True, default='')
    config_text = models.TextField(verbose_name='配置命令', null=False, blank=True, default='')
    datetime = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def __str__(self):
        return "{}-{}".format(self.vendor, self.name)

    class Meta:
        unique_together = (('vendor', 'name'),)
        verbose_name_plural = '配置片段表'
        verbose_name = '配置片段表'
        db_table = 'config_template'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['name', 'vendor'])]


# TTP模板表
class TTPTemplate(models.Model):
    vendor = models.CharField(verbose_name="厂商", choices=SupportVendor.CHOICES, default='H3C', max_length=100)
    name = models.CharField(verbose_name='名称', max_length=100, null=False, unique=True)
    ttp_content = models.TextField(verbose_name='模板内容', null=False, blank=True, default='')
    datetime = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    def __str__(self):
        return "{}-{}".format(self.vendor, self.name)

    class Meta:
        unique_together = (('vendor', 'name'),)
        verbose_name_plural = '配置片段表'
        verbose_name = '配置片段表'
        db_table = 'ttp_template'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['name', 'vendor'])]


class StructuredDriftPolicy(models.Model):
    name = models.CharField(verbose_name='策略名称', max_length=100, null=False, default='default')
    version = models.CharField(verbose_name='版本标识', max_length=100, null=False, default='v1')
    policy_content = models.JSONField(verbose_name='策略内容', null=False, blank=True, default=dict)
    is_active = models.BooleanField(verbose_name='是否激活', null=False, default=False)
    remark = models.TextField(verbose_name='备注', null=False, blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    def __str__(self):
        return '{}-{}{}'.format(self.name, self.version, ' [active]' if self.is_active else '')

    class Meta:
        verbose_name_plural = '结构化漂移策略表'
        verbose_name = '结构化漂移策略表'
        db_table = 'structured_drift_policy'
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['name', 'updated_at']),
        ]


class StructuredDriftPolicyAudit(models.Model):
    ACTION_CHOICES = (
        ('CREATE', 'CREATE'),
        ('UPDATE', 'UPDATE'),
        ('ACTIVATE', 'ACTIVATE'),
        ('ROLLBACK', 'ROLLBACK'),
        ('DELETE', 'DELETE'),
    )
    policy = models.ForeignKey(
        'StructuredDriftPolicy',
        verbose_name='目标策略',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    previous_policy = models.ForeignKey(
        'StructuredDriftPolicy',
        verbose_name='前一激活策略',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='superseded_audit_logs',
    )
    action = models.CharField(verbose_name='动作', max_length=30, choices=ACTION_CHOICES, default='UPDATE')
    actor = models.CharField(verbose_name='执行人', max_length=150, null=False, blank=True, default='')
    note = models.TextField(verbose_name='备注', null=False, blank=True, default='')
    effective_policy_before = models.JSONField(verbose_name='变更前生效策略', null=False, blank=True, default=dict)
    effective_policy_after = models.JSONField(verbose_name='变更后生效策略', null=False, blank=True, default=dict)
    effective_policy_diff = models.JSONField(verbose_name='生效策略差异摘要', null=False, blank=True, default=dict)
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)

    def __str__(self):
        return '{}-{}'.format(self.action, self.created_at)

    class Meta:
        verbose_name_plural = '结构化漂移策略审计表'
        verbose_name = '结构化漂移策略审计表'
        db_table = 'structured_drift_policy_audit'
        indexes = [
            models.Index(fields=['action', 'created_at']),
            models.Index(fields=['policy', 'created_at']),
        ]


# 配置备份表
class ConfigBackup(models.Model):
    status_choices = ((0, '在线'), (1, '下线'), (2, '挂牌'), (3, '备用'))
    config_type = (('startup', 'startup'), ('running', 'running'))
    name = models.CharField(
        verbose_name='设备名',
        max_length=100,
        null=False, default='')
    manage_ip = models.GenericIPAddressField(verbose_name='管理地址', null=False, default='0.0.0.0')
    last_time = models.DateTimeField(verbose_name='备份时间', null=False, default=timezone.now)
    idc_name = models.CharField(verbose_name='机房', max_length=100, null=True, default='')
    model_name = models.CharField(verbose_name='型号', max_length=100, null=True, default='')
    vendor = models.CharField(verbose_name='厂商', max_length=100, null=True, default='')
    file_path = models.CharField(verbose_name='文件路径', max_length=200, null=True, default='')
    config_type = models.CharField(choices=config_type, null=False, default='running', max_length=100)
    status = models.PositiveSmallIntegerField(
        verbose_name='状态', choices=status_choices, default=0)
    config_status = models.CharField(verbose_name='备份状态', max_length=100, null=False, default='')
    detail = models.TextField(verbose_name='详情', null=True, blank=True)

    def __str__(self):
        return "{}-{}".format(self.manage_ip, self.last_time)

    class Meta:
        verbose_name_plural = '配置备份表'
        verbose_name = '配置备份表'
        db_table = 'config_backup'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['manage_ip', 'last_time'])]





# 配置合规检查表
class ConfigComplianceResult(models.Model):
    compliance = models.CharField(verbose_name="结果", null=True, blank=True, max_length=100)
    manage_ip = models.GenericIPAddressField(verbose_name="设备IP", null=False, default='0.0.0.0')
    hostname = models.CharField(verbose_name="设备名", null=False, default='', max_length=200)
    vendor = models.CharField(verbose_name="厂商", null=False, default='', max_length=100)
    log_time = models.DateTimeField(verbose_name="检查时间", null=False, default=timezone.now)
    rule = models.CharField(verbose_name="检查项", null=False, default='', max_length=200)
    rule_id = models.IntegerField(verbose_name="检查项id", null=False, default=0)

    # 以下为扩展字段，便于展示详细信息和追溯
    config_file_path = models.CharField(
        verbose_name="配置文件路径",
        max_length=500,
        null=True,
        blank=True,
        help_text="本次检查所基于的配置文件存储路径",
    )
    backup_time = models.DateTimeField(
        verbose_name="配置备份时间",
        null=True,
        blank=True,
        help_text="所检查的配置备份时间，便于追溯",
    )
    config_backup_id = models.IntegerField(
        verbose_name="配置备份记录ID",
        null=True,
        blank=True,
        db_index=True,
        help_text="关联 ConfigBackup 主键，便于跳转查看备份详情",
    )
    rule_regex = models.TextField(
        verbose_name="检查规则（正则等）",
        null=True,
        blank=True,
        help_text="实际参与判断的规则摘要，如正则表达式，多条可换行",
    )
    match_detail = models.JSONField(
        verbose_name="匹配详情",
        null=True,
        blank=True,
        default=dict,
        help_text="各子规则的匹配结果，如 [{\"pattern\": \"match-compliance\", \"regex\": \"...\", \"matched\": [...]}]",
    )

    def __str__(self):
        return "{}-{}".format(self.manage_ip, self.log_time)

    class Meta:
        verbose_name_plural = '配置合规结果表'
        verbose_name = '配置合规结果表'
        db_table = 'config_compliance_result'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['log_time']),
                   models.Index(fields=['manage_ip'])]


class BackupPolicy(models.Model):
    vendor = models.CharField(verbose_name="厂商", max_length=100, null=False, default='-', blank=True)
    startup_command = models.CharField(verbose_name="启动配置命令", max_length=100, null=False, default='', blank=True)
    current_command = models.CharField(verbose_name="当前配置命令", max_length=100, null=False, default='', blank=True)
    remark = models.TextField(verbose_name="备注", null=False, blank=True, default='-')

    def __str__(self):
        return "{}-{}-{}".format(self.vendor, self.startup_command, self.current_command)

    class Meta:
        verbose_name_plural = '配置备份策略表'
        verbose_name = '配置备份策略表'
        db_table = 'config_backup_policy'  # 通过db_table自定义数据表名
        indexes = [models.Index(fields=['vendor'])]
