from django.db import models


class BlockRecord(models.Model):
    """一键封堵操作记录（审计 + 现状追踪）。"""

    class Action(models.TextChoices):
        ADD = 'add', '封堵（添加）'
        REMOVE = 'remove', '解封（删除）'

    class Status(models.TextChoices):
        PENDING = 'pending', '待执行'
        SUCCESS = 'success', '成功'
        FAILED = 'failed', '失败'

    # 封堵目标设备组
    inventory_id = models.IntegerField(verbose_name='封堵组ID')
    # 封堵的 IP/掩码列表（JSON 存储，支持多条）
    ip_mask = models.JSONField(verbose_name='封堵IP列表', default=list)
    # IP 范围（可选）
    range_start = models.CharField(max_length=64, blank=True, default='', verbose_name='范围起始IP')
    range_end = models.CharField(max_length=64, blank=True, default='', verbose_name='范围结束IP')
    # 操作类型
    action = models.CharField(
        max_length=10, choices=Action.choices, verbose_name='操作类型'
    )
    # 操作人
    operator = models.CharField(max_length=64, verbose_name='操作人')
    remote_ip = models.GenericIPAddressField(
        protocol='both', unpack_ipv4=True, null=True, blank=True, verbose_name='操作来源IP'
    )
    # 执行状态
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, verbose_name='状态'
    )
    # 关联自动化事件（AutoEvent.id）
    auto_event_id = models.IntegerField(null=True, blank=True, verbose_name='关联自动化事件ID')
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'dcs_block_record'
        verbose_name = '封堵记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operator', 'created_at'], name='idx_block_operator_time'),
            models.Index(fields=['status'], name='idx_block_status'),
            models.Index(fields=['inventory_id'], name='idx_block_inventory'),
        ]

    def __str__(self):
        return f"[{self.get_action_display()}] {self.operator} @ {self.created_at:%Y-%m-%d %H:%M}"


class DnatRecord(models.Model):
    """DNAT 公网发布记录（审计 + 当前配置快速查询）。"""

    class Status(models.TextChoices):
        ACTIVE = 'active', '生效'
        REMOVED = 'removed', '已撤销'
        FAILED = 'failed', '发布失败'

    # 设备信息
    vendor = models.CharField(max_length=20, verbose_name='厂商')
    device_ip = models.GenericIPAddressField(
        protocol='both', unpack_ipv4=True, verbose_name='设备管理IP'
    )
    # 规则信息
    rule_name = models.CharField(max_length=128, verbose_name='规则名称')
    public_ip = models.CharField(max_length=64, verbose_name='公网IP')
    private_ip = models.CharField(max_length=64, verbose_name='内网IP')
    service = models.CharField(max_length=64, verbose_name='服务对象')
    port = models.IntegerField(null=True, blank=True, verbose_name='端口')
    # 操作人
    operator = models.CharField(max_length=64, verbose_name='操作人')
    # 执行状态
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, verbose_name='状态'
    )
    # 原始请求参数（便于复现/回滚）
    raw_params = models.JSONField(verbose_name='原始请求参数', default=dict)
    # 关联 AutoFlow 记录 ID（可追溯执行过程）
    auto_flow_id = models.IntegerField(null=True, blank=True, verbose_name='关联流程记录ID')
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'dcs_dnat_record'
        verbose_name = 'DNAT 发布记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device_ip', 'status'], name='idx_dnat_device_status'),
            models.Index(fields=['public_ip'], name='idx_dnat_public_ip'),
            models.Index(fields=['operator', 'created_at'], name='idx_dnat_operator_time'),
        ]

    def __str__(self):
        return f"{self.rule_name} ({self.public_ip} → {self.private_ip})"
