from django.db import models


class InterfaceUtilizationSnapshot(models.Model):
    SCOPE_DEVICE = "device"
    SCOPE_SLOT = "slot"
    SCOPE_CHASSIS = "chassis"
    SCOPE_CHOICES = (
        (SCOPE_DEVICE, "设备级"),
        (SCOPE_SLOT, "槽位级"),
        (SCOPE_CHASSIS, "机框级"),
    )

    device_serial_num = models.CharField(max_length=200, verbose_name="设备序列号")
    manage_ip = models.GenericIPAddressField(verbose_name="管理IP")
    device_name = models.CharField(max_length=200, blank=True, default="", verbose_name="设备名称")
    component_scope = models.CharField(max_length=20, choices=SCOPE_CHOICES, default=SCOPE_DEVICE, verbose_name="分析粒度")
    component_key = models.CharField(max_length=50, blank=True, default="", verbose_name="组件标识")
    component_name = models.CharField(max_length=200, blank=True, default="", verbose_name="组件名称")
    dominant_speed = models.CharField(max_length=20, blank=True, default="", verbose_name="主端口速率")
    total_ports = models.IntegerField(default=0, verbose_name="总端口数")
    used_ports = models.IntegerField(default=0, verbose_name="已使用端口数")
    unused_ports = models.IntegerField(default=0, verbose_name="未使用端口数")
    utilization_percent = models.FloatField(default=0.0, verbose_name="利用率")
    used_speed_counts = models.JSONField(blank=True, default=dict, verbose_name="已使用速率分布")
    unused_speed_counts = models.JSONField(blank=True, default=dict, verbose_name="未使用速率分布")
    source_execute_time = models.CharField(max_length=64, blank=True, default="", verbose_name="源采集批次")
    snapshot_time = models.DateTimeField(auto_now=True, verbose_name="快照时间")

    class Meta:
        db_table = "network_analysis_interface_utilization"
        verbose_name = "接口利用率快照"
        verbose_name_plural = "接口利用率快照"
        constraints = [
            models.UniqueConstraint(
                fields=["device_serial_num", "component_scope", "component_key"],
                name="uniq_network_analysis_interface_utilization",
            )
        ]
        indexes = [
            models.Index(fields=["manage_ip", "snapshot_time"]),
            models.Index(fields=["component_scope", "utilization_percent"]),
        ]


class AddressTraceSnapshot(models.Model):
    STATUS_LOCATED = "located"
    STATUS_PARTIAL = "partial"
    STATUS_UNRESOLVED = "unresolved"
    STATUS_CHOICES = (
        (STATUS_LOCATED, "已定位"),
        (STATUS_PARTIAL, "部分定位"),
        (STATUS_UNRESOLVED, "未定位"),
    )

    ip_address = models.GenericIPAddressField(verbose_name="目标IP")
    mac_address = models.CharField(max_length=64, blank=True, default="", verbose_name="MAC地址")
    device_serial_num = models.CharField(max_length=200, blank=True, default="", verbose_name="设备序列号")
    manage_ip = models.GenericIPAddressField(verbose_name="接入设备管理IP")
    device_name = models.CharField(max_length=200, blank=True, default="", verbose_name="接入设备名称")
    idc_name = models.CharField(max_length=100, blank=True, default="", verbose_name="机房")
    category_name = models.CharField(max_length=100, blank=True, default="", verbose_name="设备类型")
    node_location = models.CharField(max_length=255, blank=True, default="", verbose_name="设备位置")
    interface_name = models.CharField(max_length=255, blank=True, default="", verbose_name="接入口")
    member_ports = models.JSONField(blank=True, default=list, verbose_name="聚合成员端口")
    trace_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNRESOLVED, verbose_name="定位状态")
    trace_method = models.CharField(max_length=50, blank=True, default="", verbose_name="定位方式")
    trace_details = models.JSONField(blank=True, default=dict, verbose_name="定位详情")
    source_execute_time = models.CharField(max_length=64, blank=True, default="", verbose_name="源采集批次")
    observed_at = models.DateTimeField(auto_now=True, verbose_name="观测时间")

    class Meta:
        db_table = "network_analysis_address_trace"
        verbose_name = "地址定位快照"
        verbose_name_plural = "地址定位快照"
        constraints = [
            models.UniqueConstraint(
                fields=["ip_address", "manage_ip", "interface_name"],
                name="uniq_network_analysis_address_trace",
            )
        ]
        indexes = [
            models.Index(fields=["ip_address", "trace_status"]),
            models.Index(fields=["manage_ip", "observed_at"]),
        ]


class AnalysisRun(models.Model):
    KIND_INTERFACE_UTILIZATION = "interface_utilization"
    KIND_ADDRESS_TRACKING = "address_tracking"
    KIND_FULL_REFRESH = "full_refresh"
    KIND_CHOICES = (
        (KIND_INTERFACE_UTILIZATION, "接口利用率分析"),
        (KIND_ADDRESS_TRACKING, "地址定位分析"),
        (KIND_FULL_REFRESH, "全量分析"),
    )

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "待执行"),
        (STATUS_RUNNING, "执行中"),
        (STATUS_SUCCESS, "成功"),
        (STATUS_FAILED, "失败"),
    )

    run_kind = models.CharField(max_length=32, choices=KIND_CHOICES, verbose_name="分析类型")
    target_manage_ip = models.GenericIPAddressField(verbose_name="目标设备IP", null=True, blank=True)
    target_ip_address = models.GenericIPAddressField(verbose_name="目标业务IP", null=True, blank=True)
    triggered_by = models.CharField(max_length=100, blank=True, default="", verbose_name="触发来源")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="执行状态")
    summary = models.JSONField(blank=True, default=dict, verbose_name="执行摘要")
    error_message = models.TextField(blank=True, default="", verbose_name="错误信息")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "network_analysis_run"
        verbose_name = "分析运行记录"
        verbose_name_plural = "分析运行记录"
        indexes = [
            models.Index(fields=["run_kind", "status"]),
            models.Index(fields=["created_at"]),
        ]
