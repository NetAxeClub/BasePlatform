from django.db import models
from django.utils import timezone


class Tasks(object):
    CHANGE = "变更"
    DNAT = "DNAT"
    SNAT = "SNAT"
    SEC_POLICY = "安全策略"
    QOS = "QOS"
    SLB = "SLB负载均衡"
    ADDRESS_SET = "地址对象"
    SERVICE_SET = "服务对象"
    DENY = "一键封堵"
    AUTO_SWITCH = "一键切换"
    INSPECTION = "巡检"

    CHOICES = (
        (CHANGE, CHANGE),
        (DNAT, DNAT),
        (SNAT, SNAT),
        (SEC_POLICY, SEC_POLICY),
        (QOS, QOS),
        (SLB, SLB),
        (DENY, DENY),
        (ADDRESS_SET, ADDRESS_SET),
        (SERVICE_SET, SERVICE_SET),
        (AUTO_SWITCH, AUTO_SWITCH),
        (INSPECTION, INSPECTION),
    )


class WorkflowHostTasks(object):
    DNAT = "DNAT"
    SNAT = "SNAT"
    SEC_POLICY = "安全策略"
    QOS = "QOS"
    SLB = "SLB负载均衡"
    ADDRESS_SET = "地址对象"
    SERVICE_SET = "服务对象"

    CHOICES = (
        (DNAT, DNAT),
        (SNAT, SNAT),
        (SEC_POLICY, SEC_POLICY),
        (QOS, QOS),
        (SLB, SLB),
        (ADDRESS_SET, ADDRESS_SET),
        (SERVICE_SET, SERVICE_SET),
    )


class InventoryTasks(object):
    CONNECTED = "网络打通"
    DENY = "一键封堵"
    INSPECTION = "巡检"

    CHOICES = (
        (DENY, DENY),
        (CONNECTED, CONNECTED),
        (INSPECTION, INSPECTION),
    )


class Method(object):
    NETCONF = "NETCONF"
    SSH = "SSH"
    RESTAPI = "RESTAPI"
    CHOICES = (
        (NETCONF, NETCONF),
        (SSH, SSH),
        (RESTAPI, RESTAPI),
    )


class State(object):
    DRAFT = "Draft"
    APPROVED = "Approved"
    PUBLISHED = "Published"
    BACKOFF = "BackOff"
    FAILED = "Failed"
    FINISH = "Finish"
    RUNNING = "running"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"

    CHOICES = (
        (DRAFT, DRAFT),
        (APPROVED, APPROVED),
        (PUBLISHED, PUBLISHED),
        (FAILED, FAILED),
        (BACKOFF, BACKOFF),
        (FINISH, FINISH),
        (RUNNING, RUNNING),
        (VERIFYING, VERIFYING),
        (SUCCEEDED, SUCCEEDED),
        (PARTIAL, PARTIAL),
        (ROLLED_BACK, ROLLED_BACK),
        (CANCELLED, CANCELLED),
    )


class WorkflowHostVar(models.Model):
    legacy_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="legacy主机变量ID")
    name = models.CharField(verbose_name="主机名", null=True, blank=True, max_length=100)
    host = models.GenericIPAddressField(verbose_name="主机IP", null=True, blank=True, max_length=100)
    variables = models.TextField(blank=True, null=True, verbose_name="主机变量")
    object_name = models.CharField(blank=True, null=True, verbose_name="对象名", max_length=100)
    description = models.CharField(blank=True, null=True, verbose_name="描述", max_length=128)
    task = models.CharField(
        verbose_name="模块",
        choices=WorkflowHostTasks.CHOICES,
        default=WorkflowHostTasks.ADDRESS_SET,
        max_length=64,
    )

    class Meta:
        db_table = "workflow_center_host_var"
        verbose_name = "工作流主机变量"
        verbose_name_plural = "工作流主机变量"


class WorkflowInventory(models.Model):
    legacy_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="legacy库存ID")
    name = models.CharField(max_length=32, unique=True, verbose_name="任务名称")
    hosts = models.ManyToManyField(
        "WorkflowHostVar",
        related_name="inventories",
        verbose_name="组内主机",
    )
    variables = models.TextField(blank=True, null=True, verbose_name="组变量")
    description = models.TextField(blank=True, null=True, verbose_name="组描述")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="添加时间")
    task = models.CharField(
        verbose_name="任务模块",
        choices=InventoryTasks.CHOICES,
        default=InventoryTasks.DENY,
        max_length=64,
    )

    class Meta:
        db_table = "workflow_center_inventory"
        verbose_name = "工作流库存"
        verbose_name_plural = "工作流库存"


class WorkflowExecution(models.Model):
    legacy_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="legacy执行ID")
    task_id = models.CharField(verbose_name="任务ID", max_length=128, default="")
    origin = models.CharField(verbose_name="来源", max_length=128, default="运维平台")
    task_result = models.TextField(verbose_name="任务结果", null=True, default=None, editable=False)
    order_code = models.CharField(verbose_name="工单", max_length=128, null=True, blank=True)
    device = models.GenericIPAddressField(verbose_name="设备IP", null=True, blank=True)
    device_id = models.IntegerField(verbose_name="设备ID", null=True, blank=True)
    commit_user = models.CharField(verbose_name="申请用户", max_length=42, default="")
    commit_time = models.DateTimeField(verbose_name="更新时间", default=timezone.localtime)
    task = models.CharField(verbose_name="任务模块", choices=Tasks.CHOICES, max_length=128, default="")
    method = models.CharField(verbose_name="配置模式", choices=Method.CHOICES, max_length=128, default="")
    class_method = models.CharField(verbose_name="类方法", max_length=128, default="")
    remote_ip = models.CharField(verbose_name="调用IP", max_length=128, null=True, blank=True)
    event = models.IntegerField(verbose_name="关联事件ID", null=True, blank=True)
    kwargs = models.TextField(blank=True, default="{}", verbose_name="任务参数")
    ttp = models.TextField(blank=True, default="{}", verbose_name="结果解析")
    commands = models.TextField(blank=True, default="[]", verbose_name="下发命令")
    back_off_commands = models.TextField(blank=True, default="[]", verbose_name="回退命令")
    state = models.CharField(default=State.DRAFT, verbose_name="流程状态", choices=State.CHOICES, max_length=200)
    code = models.IntegerField(verbose_name="状态码", default=9000, null=True, blank=True)

    def __str__(self):
        return "%s--%s--%s <task:%s>" % (
            self.task_id,
            self.commit_user,
            self.commit_time,
            self.get_task_display(),
        )

    class Meta:
        db_table = "workflow_center_execution"
        verbose_name = "工作流执行"
        verbose_name_plural = "工作流执行"


__all__ = [
    "InventoryTasks",
    "Method",
    "State",
    "Tasks",
    "WorkflowExecution",
    "WorkflowHostTasks",
    "WorkflowHostVar",
    "WorkflowInventory",
]
