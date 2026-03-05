import json
import logging
from django.db import models
from .processors import get_processor

logger = logging.getLogger(__name__)


class DeviceCollectionPlans(models.Model):
    """采集汇总方案"""
    VENDOR_CHOICES = [
        ('H3C', '华三'),
        ('Huawei', '华为'),
        ('Ruijie', '锐捷'),
        ('Hillstone', '山石'),
        ('Cisco', '思科'),
        ('Mellanox', 'Mellanox'),
        ('ZTE', '中兴'),
        ('centec', '盛科'),
        ('colasoft', '科来'),
        ('DELL', '戴尔'),
        ('F5', 'F5'),
        ('Maipu', '迈普'),
        ('Citrix', 'Citrix'),
        ('sangfor', '深信服'),
        ('inspur', '浪潮思科'),
        ('nsfocus', '绿盟'),
        ('nettap', '成都数维'),
        ('TJX', '腾捷兴')
    ]
    name = models.CharField(max_length=100, verbose_name='父采集方案名称', unique=True)
    vendor = models.CharField(max_length=30, choices=VENDOR_CHOICES, verbose_name='厂商')
    device_type = models.CharField(max_length=30, verbose_name='设备类型')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '父采集方案'
        verbose_name_plural = '父采集方案'
        db_table = 'device_api_collection_plans'
        ordering = ['name', 'created_at']

    def __str__(self):
        return f"{self.name} ({self.get_vendor_display()})"


class DeviceSubCollectionPlan(models.Model):
    """子采集方案模型"""
    summary_plan = models.ForeignKey(
        DeviceCollectionPlans,
        on_delete=models.CASCADE,
        related_name='collect_plans',
        verbose_name='采集汇总方案'
    )

    # 基本信息
    name = models.CharField(max_length=50, verbose_name='子采集方案名称', unique=True)
    collection_type = models.CharField(max_length=20, default='arp', verbose_name='采集类型')
    description = models.TextField(blank=True, verbose_name='方案描述')

    # 采集方式配置,Netmiko配置（新建时默认关闭，由用户在前端按需开启）
    netmiko_enabled = models.BooleanField(default=False, verbose_name='启用Netmiko')
    netmiko_method = models.CharField(blank=True, max_length=100, default='', verbose_name='Netmiko方法名称',
                                      help_text='要执行的采集方法名称')
    netmiko_path = models.CharField(blank=True, max_length=150, default='', verbose_name='Netmiko路径')
    netmiko_field_mappings = models.JSONField(blank=True, default=dict, verbose_name='Netmiko字段映射配置')
    netmiko_processor_enabled = models.BooleanField(default=False, verbose_name='Netmiko是否启用数据处理')
    netmiko_processor = models.TextField(blank=True, null=True, verbose_name='Netmiko数据处理代码')

    # NETCONF配置
    netconf_enabled = models.BooleanField(default=False, verbose_name='启用NETCONF')
    netconf_path = models.CharField(blank=True, max_length=150, default='', verbose_name='NETCONF路径')
    netconf_field_mappings = models.JSONField(blank=True, default=dict, verbose_name='NETCONF字段映射配置')
    netconf_processor_enabled = models.BooleanField(default=False, verbose_name='NETCONF是否启用数据处理')
    netconf_processor = models.TextField(blank=True, null=True, verbose_name='NETCONF数据处理代码')

    # SNMP配置
    snmp_enabled = models.BooleanField(default=False, verbose_name='启用SNMP')
    snmp_version = models.CharField(blank=True, max_length=10, default='v2c', verbose_name='SNMP版本', 
                                    choices=[('v1', 'v1'), ('v2c', 'v2c'), ('v3', 'v3')])
    snmp_oids = models.JSONField(blank=True, default=list, verbose_name='SNMP OID列表',
                                  help_text='OID列表，如: ["1.3.6.1.2.1.4.22.1.2", "1.3.6.1.2.1.4.22.1.3"]')
    snmp_path = models.CharField(blank=True, max_length=150, default='', verbose_name='SNMP路径')
    snmp_field_mappings = models.JSONField(blank=True, default=dict, verbose_name='SNMP字段映射配置')
    snmp_processor_enabled = models.BooleanField(default=False, verbose_name='SNMP是否启用数据处理')
    snmp_processor = models.TextField(blank=True, null=True, verbose_name='SNMP数据处理代码')

    # RESTCONF配置
    restconf_enabled = models.BooleanField(default=False, verbose_name='启用RESTCONF')
    restconf_endpoint = models.CharField(blank=True, max_length=500, default='', verbose_name='RESTCONF端点路径')
    restconf_method = models.CharField(blank=True, max_length=10, default='GET', verbose_name='HTTP方法',
                                       choices=[('GET', 'GET'), ('POST', 'POST'), ('PUT', 'PUT'), ('DELETE', 'DELETE')])
    restconf_path = models.CharField(blank=True, max_length=150, default='', verbose_name='RESTCONF路径')
    restconf_field_mappings = models.JSONField(blank=True, default=dict, verbose_name='RESTCONF字段映射配置')
    restconf_processor_enabled = models.BooleanField(default=False, verbose_name='RESTCONF是否启用数据处理')
    restconf_processor = models.TextField(blank=True, null=True, verbose_name='RESTCONF数据处理代码')

    # Telemetry配置
    telemetry_enabled = models.BooleanField(default=False, verbose_name='启用Telemetry')
    telemetry_subscription_path = models.CharField(blank=True, max_length=500, default='', verbose_name='Telemetry订阅路径')
    telemetry_sampling_interval = models.IntegerField(default=10, verbose_name='采样间隔（秒）')
    telemetry_data_format = models.CharField(blank=True, max_length=20, default='json', verbose_name='数据格式',
                                              choices=[('gpb', 'GPB'), ('json', 'JSON')])
    telemetry_path = models.CharField(blank=True, max_length=150, default='', verbose_name='Telemetry路径')
    telemetry_field_mappings = models.JSONField(blank=True, default=dict, verbose_name='Telemetry字段映射配置')
    telemetry_processor_enabled = models.BooleanField(default=False, verbose_name='Telemetry是否启用数据处理')
    telemetry_processor = models.TextField(blank=True, null=True, verbose_name='Telemetry数据处理代码')

    # TextFSM配置
    textfsm_template = models.CharField(blank=True, max_length=100, default='', verbose_name='TextFSM模板路径')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '子采集方案'
        verbose_name_plural = '子采集方案'
        db_table = 'device_api_sub_collection_plans'
        ordering = ['name', 'created_at']
        indexes = [
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.name}"

    def get_netmiko_method(self):
        """获取Netmiko方法名称"""
        return self.netmiko_method.strip() if self.netmiko_method else ''

    def get_netmiko_field_mappings_dict(self):
        """获取Netmiko字段映射字典"""
        if isinstance(self.netmiko_field_mappings, str):
            return json.loads(self.netmiko_field_mappings)
        return {}

    def get_netconf_field_mappings_dict(self):
        """获取NETCONF字段映射字典"""
        if isinstance(self.netconf_field_mappings, str):
            return json.loads(self.netconf_field_mappings)
        return {}

    def validate_field_mappings(self):
        """验证字段映射格式"""
        errors = []

        # 验证Netmiko字段映射
        if self.netmiko_enabled and self.netmiko_field_mappings:
            if not isinstance(self.netmiko_field_mappings, dict):
                errors.append("Netmiko字段映射格式不正确，应为字典格式")

        # 验证NETCONF字段映射
        if self.netconf_enabled and self.netconf_field_mappings:
            if not isinstance(self.netconf_field_mappings, dict):
                errors.append("NETCONF字段映射格式不正确，应为字典格式")

        return errors

    def _process_data(self, processor_enabled: bool, processor_code: str, data, method: str = 'netmiko'):
        """
        数据处理核心逻辑：
        当 processor_enabled 为 False 或 processor_code 为空时，不执行自定义处理器，直接返回原始数据，
        由调用方仅使用字段映射做结构化转换（符合「字段映射」改造约定）。
        1. 优先寻找并执行预定义的处理器方法（推荐方式，支持复杂逻辑与IDE维护）
        2. 如果未找到预定义处理器，则尝试执行数据库中存储的动态代码（兼容旧方案）
        """
        # 未启用或代码为空时，跳过自定义代码，仅由字段映射处理
        if not processor_enabled or not (processor_code and str(processor_code).strip()):
            return data

        vendor = self.summary_plan.vendor
        device_type = self.summary_plan.device_type
        collection_type = self.collection_type

        # 1. 尝试使用注册的处理器
        processor_func = get_processor(vendor, device_type, collection_type, method)
        if processor_func:
            try:
                logger.info(f"执行预定义处理器: {vendor}:{device_type}:{collection_type}:{method}")
                return processor_func(data)
            except Exception as e:
                logger.error(f"预定义处理器执行失败: {str(e)}", exc_info=True)
                return data

        # 2. 兼容性回退：执行数据库中的动态代码
        # if processor_enabled and processor_code:
        #     try:
        #         logger.info(f"执行动态代码处理器: {self.name} ({method})")
        #         local_vars = {'data': data}
        #         # 在安全的局部命名空间中执行
        #         exec(processor_code, globals(), local_vars)
        #
        #         if 'process_data' in local_vars and callable(local_vars['process_data']):
        #             result = local_vars['process_data'](data)
        #             return result if result is not None else data
        #
        #         logger.warning(f"动态代码中未找到有效的 'process_data' 函数: {self.name}")
        #     except Exception as e:
        #         logger.error(f"动态代码处理执行异常: {str(e)}", exc_info=True)

        return data

    def process_netmiko_data(self, data):
        """处理采集到的数据"""
        return self._process_data(self.netmiko_processor_enabled, self.netmiko_processor, data, method='netmiko')

    def process_netconf_data(self, data):
        """处理采集到的数据"""
        return self._process_data(self.netconf_processor_enabled, self.netconf_processor, data, method='netconf')

    def save(self, *args, **kwargs):
        """保存时确保字段映射有正确的默认值"""
        # 确保字段映射字段有默认值
        if not self.netmiko_field_mappings:
            self.netmiko_field_mappings = {}
        if not self.netconf_field_mappings:
            self.netconf_field_mappings = {}
        if not self.snmp_field_mappings:
            self.snmp_field_mappings = {}
        if not self.restconf_field_mappings:
            self.restconf_field_mappings = {}
        if not self.telemetry_field_mappings:
            self.telemetry_field_mappings = {}
        if not self.snmp_oids:
            self.snmp_oids = []

        super().save(*args, **kwargs)


class NetconfXMLTemplate(models.Model):
    """NETCONF XML模板模型"""
    COLLECT_METHOD_CHOICES = [
        ('rpc', 'RPC'),
        ('get', 'GET'),
        ('get_config', 'GET_CONFIG'),
    ]
    collect_method = models.CharField(
        max_length=20,
        choices=COLLECT_METHOD_CHOICES,
        verbose_name='采集方法'
    )
    xml_template = models.TextField(verbose_name='XML模板内容')
    description = models.TextField(blank=True, null=True, verbose_name='模板描述')
    collection_plan = models.ForeignKey(
        DeviceSubCollectionPlan,
        on_delete=models.CASCADE,
        related_name='xml_templates',
        verbose_name='子采集方案'
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'device_api_netconf_xml_template'
        verbose_name = 'NETCONF XML模板'
        verbose_name_plural = 'NETCONF XML模板'
        ordering = ['collection_plan', 'created_at']
        indexes = [
            models.Index(fields=['collection_plan']),
            models.Index(fields=['collect_method']),
        ]
        unique_together = ['collection_plan', 'collect_method']  # 同一采集方案下采集方法唯一

    def __str__(self):
        return f"{self.collect_method} ({self.collection_plan.name})"


class PlansToDevice(models.Model):
    """方案与设备关联：支持本地采集或南向驱动采集，二选一，默认本地采集。"""
    manage_ip = models.CharField(verbose_name="设备IP", max_length=100, null=False, blank=False)
    plan = models.ForeignKey("DeviceCollectionPlans", on_delete=models.SET_NULL, null=True, related_name="device_plan",
                             verbose_name="关联方案")
    # 采集模式：True=本地采集，False=南向驱动采集（此时需填写 execute_node）
    use_local = models.BooleanField(
        default=True,
        verbose_name="使用本地采集",
        help_text="默认True表示本地采集；设为False时使用南向驱动，由 execute_node 指定执行节点",
    )
    # 南向驱动执行节点（当 use_local=False 时使用）
    execute_node = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name="南向驱动执行节点",
        help_text="仅当 use_local=False 时生效，指定南向驱动节点地址或标识",
    )
    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '采集方案关系表'
        verbose_name_plural = '采集方案关系表'
        db_table = 'device_api_plan2device'
        ordering = ['manage_ip', 'created_at']
        # unique_together = (("name", "vendor"),)

    def __str__(self):
        return f"{self.manage_ip} ({self.plan.name})"
