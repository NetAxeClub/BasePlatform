from django.db import models
from simple_history.models import HistoricalRecords
from django.db.models.signals import pre_save
from django.dispatch import receiver
import xml.etree.ElementTree as ET
import json


# Create your models here.


# 设备信息采集方案
class CollectionPlan(models.Model):
    CATEGORY_CHOICES = (
        ('交换机', '交换机'),
        ('防火墙', '防火墙'),
        ('路由器', '路由器')
    )
    vendor = models.CharField(
        verbose_name='厂商', max_length=50, default='H3C')
    category = models.CharField(
        verbose_name='类型', choices=CATEGORY_CHOICES, max_length=50, default='交换机')
    name = models.CharField(verbose_name='采集方案',
                            max_length=100, null=True, blank=True)
    commands = models.TextField(
        blank=True, default='[]',
        verbose_name='下发命令',
    )
    netconf_method = models.TextField(
        blank=True, default='[]',
        verbose_name='方法列表',
    )
    memo = models.TextField(verbose_name='备注', null=True, blank=True)
    netconf_class = models.CharField(
        verbose_name="Netconf连接类", null=True, blank=True, max_length=100)

    def get_commands(self):
        return '\n'.join(json.loads(self.commands))

    def get_netconf_method(self):
        return '\n'.join(json.loads(self.netconf_method))

    def __str__(self):
        return '%s' % self.name

    class Meta:
        unique_together = (("name", "vendor"),)
        verbose_name = '设备数据采集方案'
        verbose_name_plural = '设备数据采集方案表'
        db_table = 'device_collection_plan'  # 通过db_table自定义数据表名


# 采集规则-解析插件
# class CollectionParsePlugin(models.Model):
#     PLUGIN_CHOICES = (
#         ('TextFSM', 'TextFSM'),
#         ('TTP', 'TTP'),
#     )
#     id = models.BigAutoField(primary_key=True)
#     # method = models.CharField(verbose_name='解析方式', choices=PLUGIN_CHOICES, max_length=50, default='TextFSM')
#     # template = models.TextField(verbose_name='解析模板', default='', null=True, blank=True)
#     # # 如果指定了走指定插件，没指定走默认BatMan中和vendor关联的插件
#     plugin = models.CharField(verbose_name='数据处理插件', max_length=50, null=True, blank=True)
#
#     class Meta:
#         # unique_together = (("module", "method"),)
#         verbose_name = '解析插件表'
#         verbose_name_plural = '解析插件表'
#         db_table = 'collection_parse_plugin'  # 通过db_table自定义数据表名


# 采集规则-匹配方法
class CollectionMatchRule(models.Model):
    """
    __exact: 精确匹配字段的值。它表示只返回与指定值完全相等的数据。
    __iexact：不区分大小写的精确匹配
    __contains：包含指定值的数据
    __icontains：不区分大小写，包含指定值的数据
    __startswith：以指定值开头的数据
    __istartswith：不区分大小写，以指定值开头的数据
    __endswith：以指定值结尾的数据
    __iendswith：不区分大小写，以指定值结尾的数据
    """
    OPER_CHOICES = (
        ('__exact', '精确匹配'),
        ('__iexact', '不区分大小写的精确匹配'),
        ('__contains', '包含指定值'),
        ('__icontains', '不区分大小写包含指定值'),
        ('__startswith', '以指定值开头'),
        ('__endswith', '以指定值结尾'),
        ('__istartswith', '不区分大小写以指定值开头'),
        ('__iendswith', '不区分大小写以指定值结尾'),
    )
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(verbose_name='规则名', max_length=10,  blank=True)
    fields = models.CharField(verbose_name='匹配字段', max_length=50, default='', blank=True, null=True)
    operator = models.CharField(verbose_name='操作符', choices=OPER_CHOICES, max_length=50, null=True, default='__exact', blank=True)
    value = models.CharField(verbose_name='匹配值', max_length=50, default='', blank=True, null=True)
    rule = models.ForeignKey("automation.CollectionRule", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name='match_rule')

    def __str__(self):
        OPERATOR_MAPPING = dict(self.OPER_CHOICES)
        operator_name = OPERATOR_MAPPING.get(self.operator, '')
        return "{}-{}-{}-{}".format(self.name, self.fields, operator_name, self.value)

    class Meta:
        indexes = [models.Index(fields=['id', ])]
        unique_together = (("rule", "name"),)
        verbose_name = '采集规则匹配方法表'
        verbose_name_plural = '采集规则匹配方法表'
        db_table = 'collection_match_rule'  # 通过db_table自定义数据表名


@receiver(pre_save, sender=CollectionMatchRule)
def auto_match_rule_name(sender, instance, **kwargs):
    if not instance.name:
        last_instance = sender.objects.select_related('rule').filter(rule=instance.rule).order_by('-id').first()
        if last_instance:
            last_id = ord(last_instance.name)
            new_id = chr(last_id + 1)
            instance.name = new_id
        else:
            instance.name = 'A'


# 采集规则
class CollectionRule(models.Model):
    MODULE_CHOICES = (
        ('BASE', '基础平台'),
        ('SouthDriver', '南向驱动'),
    )
    METHOD_CHOICES = (
        ('NETCONF', 'NETCONF'),
        ('CLI', 'CLI'),
        ('REST_API', 'REST_API'),
    )
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(verbose_name='规则名', max_length=100, default='', null=True, blank=True)
    operation = models.CharField(verbose_name='运算符', max_length=50, default='', null=True, blank=True)
    module = models.CharField(verbose_name='执行模块', choices=MODULE_CHOICES, max_length=50, default='BASE')
    method = models.CharField(verbose_name='执行方法', choices=METHOD_CHOICES, max_length=50, default='CLI')
    execute = models.TextField(blank=True, default='', verbose_name='执行内容')
    plugin = models.CharField(verbose_name="解析插件标识", max_length=50, null=False, blank=False, default='')

    @staticmethod
    def is_valid_xml(xml_string):
        try:
            ET.fromstring(xml_string)
            return True
        except ET.ParseError:
            return False

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        # 先执行格式校验
        if self.method == 'CLI':
            if not isinstance(self.execute, str):
                raise ValueError("命令校验失败，CLI校验内容不是标准命令行.")
        elif self.method == 'NETCONF':
            if not CollectionRule.is_valid_xml(self.execute):
                raise ValueError("命令校验失败，NETCONF校验内容不符合XML规范.")
        elif self.method == 'REST_API':
            if not isinstance(json.loads(self.execute), dict):
                raise ValueError("命令校验失败，REST_API校验内容不是dict类型.")
        # 最后执行父类方法
        super(CollectionRule, self).save()

    class Meta:
        indexes = [models.Index(fields=['id', ])]
        # unique_together = (("module", "method"),)
        verbose_name = '采集规则表'
        verbose_name_plural = '采集规则表'
        db_table = 'collection_rule'  # 通过db_table自定义数据表名


# 任务模块
class Tasks(object):
    DNAT = 'DNAT'
    SNAT = 'SNAT'
    SEC_POLICY = '安全策略'
    QOS = 'QOS'
    SLB = 'SLB负载均衡'
    ADDRESS_SET = '地址对象'
    SERVICE_SET = '服务对象'
    DENY = '一键封堵'

    CHOICES = (
        (DNAT, DNAT),
        (SNAT, SNAT),
        (SEC_POLICY, SEC_POLICY),
        (QOS, QOS),
        (SLB, SLB),
        (DENY, DENY),
        (ADDRESS_SET, ADDRESS_SET),
        (SERVICE_SET, SERVICE_SET),
    )


# 任务模块
class AutoTasks(object):
    DNAT = 'DNAT'
    SNAT = 'SNAT'
    SEC_POLICY = '安全策略'
    QOS = 'QOS'
    SLB = 'SLB负载均衡'
    ADDRESS_SET = '地址对象'
    SERVICE_SET = '服务对象'

    CHOICES = (
        (DNAT, DNAT),
        (SNAT, SNAT),
        (SEC_POLICY, SEC_POLICY),
        (QOS, QOS),
        (SLB, SLB),
        (ADDRESS_SET, ADDRESS_SET),
        (SERVICE_SET, SERVICE_SET),
    )


# 编排任务模块
class InventoryTasks(object):
    CONNECTED = '网络打通'
    DENY = '一键封堵'

    CHOICES = (
        (DENY, DENY),
        (CONNECTED, CONNECTED),
    )


# 配置模式
class Method(object):
    NETCONF = 'NETCONF'
    SSH = 'SSH'
    RESTAPI = 'RESTAPI'
    CHOICES = (
        (NETCONF, NETCONF),
        (SSH, SSH),
        (RESTAPI, RESTAPI)
    )


# 自动化流程状态
class State(object):
    """
    Constants to represent the `state`s of the PublishableModel
    """
    DRAFT = 'Draft'  # 早期阶段
    APPROVED = 'Approved'  # 经核准的
    PUBLISHED = 'Published'  # 生效
    BACKOFF = 'BackOff'  # 回退
    FAILED = 'Failed'  # 失败
    FINISH = 'Finish'  # 闭环

    CHOICES = (
        (DRAFT, DRAFT),
        (APPROVED, APPROVED),
        (PUBLISHED, PUBLISHED),
        (FAILED, FAILED),
        (BACKOFF, BACKOFF),
        (FINISH, FINISH),
    )


# 自动化主机变量
class AutoVars(models.Model):
    ans_name = models.CharField(verbose_name='主机名', null=True, blank=True, max_length=32)
    ans_host = models.GenericIPAddressField(verbose_name='主机IP', null=True, blank=True, max_length=32)
    ans_vars = models.TextField(blank=True, null=True, verbose_name='主机变量')
    ans_obj = models.CharField(blank=True, null=True, verbose_name='对象名', max_length=32)
    ans_memo = models.CharField(blank=True, null=True, verbose_name='描述', max_length=128)
    task = models.CharField(verbose_name='模块', choices=AutoTasks.CHOICES, default=AutoTasks.ADDRESS_SET, max_length=64,
                            null=False)


# 自动化任务场景清单
class AutomationInventory(models.Model):
    ans_group_name = models.CharField(max_length=32, unique=True, verbose_name='任务名称')
    ans_group_hosts = models.ManyToManyField("AutoVars", related_name='to_inventory', verbose_name='组内主机')
    ans_group_vars = models.TextField(blank=True, null=True, verbose_name='组变量')
    ans_group_memo = models.TextField(blank=True, null=True, verbose_name='组描述')
    ans_group_datetime = models.DateTimeField(auto_now_add=True, verbose_name='添加时间')
    task = models.CharField(verbose_name='任务模块', choices=InventoryTasks.CHOICES, default=InventoryTasks.DENY,
                            max_length=64, null=False)


class AutoFlow(models.Model):
    task_id = models.CharField(verbose_name='任务ID', max_length=128, null=False, default='')
    origin = models.CharField(verbose_name='来源', max_length=128, null=False, default='运维平台')
    task_result = models.TextField(verbose_name='任务结果', null=True, default=None, editable=False)
    order_code = models.CharField(verbose_name='工单', max_length=128, null=True, blank=True)
    device = models.GenericIPAddressField(verbose_name='设备IP', null=True, blank=True)
    # 后续自动化任务能够根据这个ID拿到唯一的CMDB条目
    device_id = models.IntegerField(verbose_name='设备ID', null=True, blank=True)
    commit_user = models.CharField(verbose_name='申请用户', max_length=42, null=False, default='')
    commit_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    task = models.CharField(verbose_name='任务模块', choices=Tasks.CHOICES, max_length=128, null=False, default='')
    method = models.CharField(verbose_name='配置模式', choices=Method.CHOICES, max_length=128, null=False, default='')
    class_method = models.CharField(verbose_name='类方法', null=False, max_length=128, default='')
    remote_ip = models.CharField(verbose_name='调用IP', max_length=128, null=True, blank=True)
    event = models.ForeignKey('AutoEvent', on_delete=models.CASCADE, related_name='subs', null=True, blank=True,
                              verbose_name='关联事件')
    kwargs = models.TextField(
        blank=True, default='{}',
        verbose_name='任务参数',
    )
    ttp = models.TextField(
        blank=True, default='{}',
        verbose_name='结果解析',
    )
    commands = models.TextField(
        blank=True, default='[]',
        verbose_name='下发命令',
    )
    back_off_commands = models.TextField(
        blank=True, default='[]',
        verbose_name='回退命令',
    )
    state = models.CharField(default=State.DRAFT, verbose_name='流程状态', choices=State.CHOICES, max_length=200)
    code = models.IntegerField(verbose_name='状态码', default=9000, null=True, blank=True)

    # 判断是否失败状态
    def is_failed(self):
        return self.state == State.FAILED

    # 流程打回
    def unapprove(self, by=None):
        """恢复到批准状态(流程打回)"""
        self.code = 9000

    # 流程批准，状态转换
    def approve(self, by=None):
        """经过审查后得到批准"""
        self.code = 9002

    # 流程初始化失败
    def draft_failed(self, by=None):
        """初始化失败"""
        self.code = 9003

    # 准备执行 任务发布
    def publish(self, by=None):
        self.state = State.PUBLISHED
        self.code = 9006

    # 发布 -> 完成工单闭环
    def finish(self, by=None):
        self.code = 9008

    # 发布 -> 回退
    def back_off(self, by=None):
        self.code = 9004

    # 执行完成 -> 失败
    def failed(self, by=None):
        self.code = 9005

    # 执行失败 -> 回退
    def failed_back_off(self, by=None):
        self.code = 9007

    # 执行回退 -> 失败
    def back_off_failed(self, by=None):
        self.code = 9009

    def __str__(self):
        return '%s--%s--%s <task:%s>' % (self.task_id, self.commit_user, self.commit_time, self.get_task_display())

    class Meta:
        verbose_name = '自动化流程表'
        verbose_name_plural = "自动化流程表"
        db_table = 'auto_work_flow'


# 自动化事件
class AutoEvent(models.Model):
    commit_user = models.CharField(verbose_name='申请用户', max_length=42, null=False, default='')
    remote_ip = models.CharField(verbose_name='调用IP', max_length=128, null=True, blank=True)
    task = models.CharField(verbose_name='任务模块', choices=Tasks.CHOICES, max_length=128, null=False, default='')
    commit_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')