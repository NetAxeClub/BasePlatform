import json
import logging
import xml.etree.ElementTree as ET
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .processors import get_processor

logger = logging.getLogger(__name__)

VENDOR_NAME_FALLBACKS = {
    "H3C": "华三",
    "Huawei": "华为",
    "Ruijie": "锐捷",
    "Hillstone": "山石网科",
    "Cisco": "思科",
    "ZTE": "中兴",
    "centec": "盛科",
    "colasoft": "科来",
    "Mellanox": "Mellanox",
    "DELL": "戴尔",
    "F5": "F5",
    "Maipu": "迈普",
    "Citrix": "Citrix",
    "sangfor": "深信服",
    "inspur": "浪潮思科",
    "nsfocus": "绿盟",
    "nettap": "成都数维",
    "TJX": "腾捷兴",
}
VENDOR_ALIAS_FALLBACKS = {
    value: key for key, value in VENDOR_NAME_FALLBACKS.items()
}
DEVICE_TYPE_NAME_FALLBACKS = {
    "switch": "交换机",
    "firewall": "防火墙",
    "router": "路由器",
    "tap交换机": "TAP交换机",
    "TAP交换机": "TAP交换机",
}
DEVICE_TYPE_ALIAS_FALLBACKS = {
    "交换机": "switch",
    "防火墙": "firewall",
    "路由器": "router",
    "TAP交换机": "switch",
}


class PlatformProfile(models.Model):
    """设备平台画像，用于按厂商/产品线/版本选择默认方案与采集能力。"""

    code = models.CharField(max_length=64, unique=True, verbose_name="画像编码")
    vendor_alias = models.CharField(max_length=30, verbose_name="厂商别名")
    category = models.CharField(max_length=30, blank=True, default="", verbose_name="设备类型")
    series_patterns = models.JSONField(blank=True, default=list, verbose_name="型号匹配规则")
    os_family = models.CharField(max_length=64, blank=True, default="", verbose_name="操作系统族")
    version_patterns = models.JSONField(blank=True, default=list, verbose_name="版本匹配规则")
    preferred_methods = models.JSONField(blank=True, default=dict, verbose_name="优先采集协议")
    fallback_methods = models.JSONField(blank=True, default=dict, verbose_name="回退采集协议")
    supported_collection_types = models.JSONField(
        blank=True, default=list, verbose_name="支持的采集类型"
    )
    default_plan_name = models.CharField(max_length=100, blank=True, default="", verbose_name="默认方案名")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "平台画像"
        verbose_name_plural = "平台画像"
        db_table = "device_api_platform_profile"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["vendor_alias", "category"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.code


class DeviceDiscoveryState(models.Model):
    """设备发现运行态，不放入 asset 主表，避免污染资产事实模型。"""

    device_serial_num = models.CharField(max_length=200, unique=True, verbose_name="设备序列号")
    manage_ip = models.GenericIPAddressField(verbose_name="管理IP", null=True, blank=True)
    profile_code = models.CharField(max_length=64, blank=True, default="", verbose_name="画像编码")
    capability_facts = models.JSONField(blank=True, default=dict, verbose_name="能力画像事实")
    last_discovered_at = models.DateTimeField(null=True, blank=True, verbose_name="最近发现时间")
    last_discovery_status = models.CharField(max_length=20, blank=True, default="pending", verbose_name="最近发现状态")
    last_discovery_error = models.TextField(blank=True, default="", verbose_name="最近发现错误")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "设备发现状态"
        verbose_name_plural = "设备发现状态"
        db_table = "device_api_device_discovery_state"
        indexes = [
            models.Index(fields=["manage_ip"]),
            models.Index(fields=["profile_code", "last_discovery_status"]),
        ]

    def __str__(self):
        return self.device_serial_num


class DeviceCollectionPlans(models.Model):
    """采集汇总方案"""
    PLAN_KIND_TEMPLATE = "template"
    PLAN_KIND_RUNTIME = "runtime"
    COLLECTION_METHOD_NETMIKO = "netmiko"
    COLLECTION_METHOD_NETCONF = "netconf"
    COLLECTION_METHOD_BOTH = "both"
    PLAN_KIND_CHOICES = [
        (PLAN_KIND_TEMPLATE, "模板方案"),
        (PLAN_KIND_RUNTIME, "运行时方案"),
    ]
    COLLECTION_METHOD_CHOICES = [
        (COLLECTION_METHOD_NETMIKO, "仅 Netmiko"),
        (COLLECTION_METHOD_NETCONF, "仅 NETCONF"),
        (COLLECTION_METHOD_BOTH, "Netmiko + NETCONF"),
    ]

    name = models.CharField(max_length=100, verbose_name='父采集方案名称', unique=True)
    vendor = models.CharField(max_length=30, verbose_name='厂商')
    device_type = models.CharField(max_length=30, verbose_name='设备类型')
    description = models.TextField(blank=True, null=True, verbose_name='描述')
    profile_code = models.CharField(max_length=64, blank=True, default="", verbose_name="画像编码")
    plan_kind = models.CharField(
        max_length=16,
        choices=PLAN_KIND_CHOICES,
        default=PLAN_KIND_RUNTIME,
        verbose_name="方案类型",
    )
    generated_by_system = models.BooleanField(default=False, verbose_name="是否系统生成")
    version = models.PositiveIntegerField(default=1, verbose_name="方案版本")
    is_default = models.BooleanField(default=False, verbose_name="是否默认方案")
    enabled_collection_types = models.JSONField(blank=True, default=list, verbose_name="启用的采集类型")
    collection_method = models.CharField(
        max_length=16,
        choices=COLLECTION_METHOD_CHOICES,
        default=COLLECTION_METHOD_NETMIKO,
        verbose_name="方案级采集方式",
    )
    is_active = models.BooleanField(default=True, verbose_name='是否启用')

    # 时间戳
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '父采集方案'
        verbose_name_plural = '父采集方案'
        db_table = 'device_api_collection_plans'
        ordering = ['name', 'created_at']
        indexes = [
            models.Index(fields=["profile_code", "device_type"]),
            models.Index(fields=["vendor", "is_default"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_vendor_display()})"

    @classmethod
    def resolve_vendor_record(cls, vendor_value):
        from apps.asset.models import Vendor

        normalized_value = str(vendor_value or "").strip()
        if not normalized_value:
            return None

        vendor = Vendor.objects.filter(name=normalized_value).first()
        if vendor:
            return vendor
        return Vendor.objects.filter(alias=normalized_value).first()

    @classmethod
    def normalize_vendor_value(cls, vendor_value: str) -> str:
        normalized_value = str(vendor_value or "").strip()
        if not normalized_value:
            return ""

        fallback_name = VENDOR_NAME_FALLBACKS.get(normalized_value)
        if fallback_name:
            return fallback_name
        if normalized_value in VENDOR_ALIAS_FALLBACKS:
            return normalized_value

        vendor = cls.resolve_vendor_record(normalized_value)
        if vendor:
            return str(vendor.name or "").strip()
        return normalized_value

    @classmethod
    def resolve_vendor_alias(cls, vendor_value: str) -> str:
        normalized_value = str(vendor_value or "").strip()
        if not normalized_value:
            return ""

        fallback_alias = VENDOR_ALIAS_FALLBACKS.get(normalized_value)
        if fallback_alias:
            return fallback_alias
        if normalized_value in VENDOR_NAME_FALLBACKS:
            return normalized_value

        vendor = cls.resolve_vendor_record(normalized_value)
        if vendor and getattr(vendor, "alias", ""):
            return str(vendor.alias or "").strip()
        return normalized_value

    @classmethod
    def resolve_vendor_variants(cls, vendor_value: str):
        normalized_value = str(vendor_value or "").strip()
        if not normalized_value:
            return []

        variants = []
        for value in (
            normalized_value,
            cls.normalize_vendor_value(normalized_value),
            cls.resolve_vendor_alias(normalized_value),
        ):
            value = str(value or "").strip()
            if value and value not in variants:
                variants.append(value)
        return variants

    @property
    def vendor_alias(self) -> str:
        return self.resolve_vendor_alias(self.vendor)

    def get_vendor_display(self):
        return self.normalize_vendor_value(self.vendor) or self.vendor

    @classmethod
    def resolve_device_type_record(cls, device_type_value):
        from apps.asset.models import Category

        normalized_value = str(device_type_value or "").strip()
        if not normalized_value:
            return None

        candidate_names = [normalized_value]
        fallback_name = DEVICE_TYPE_NAME_FALLBACKS.get(normalized_value)
        if fallback_name and fallback_name not in candidate_names:
            candidate_names.append(fallback_name)

        for candidate_name in candidate_names:
            category = Category.objects.filter(name=candidate_name).first()
            if category:
                return category
        return None

    @classmethod
    def normalize_device_type_value(cls, device_type_value: str) -> str:
        normalized_value = str(device_type_value or "").strip()
        if not normalized_value:
            return ""

        fallback_name = DEVICE_TYPE_NAME_FALLBACKS.get(normalized_value)
        if fallback_name:
            return fallback_name
        if normalized_value in DEVICE_TYPE_ALIAS_FALLBACKS:
            return normalized_value

        category = cls.resolve_device_type_record(normalized_value)
        if category:
            return str(category.name or "").strip()
        return normalized_value

    @classmethod
    def resolve_device_type_alias(cls, device_type_value: str) -> str:
        normalized_value = str(device_type_value or "").strip()
        if not normalized_value:
            return ""

        fallback_alias = DEVICE_TYPE_ALIAS_FALLBACKS.get(normalized_value)
        if fallback_alias:
            return fallback_alias
        if normalized_value in DEVICE_TYPE_NAME_FALLBACKS:
            return normalized_value

        category = cls.resolve_device_type_record(normalized_value)
        if category:
            category_name = str(category.name or "").strip()
            return DEVICE_TYPE_ALIAS_FALLBACKS.get(category_name, category_name)
        return normalized_value

    @classmethod
    def resolve_device_type_variants(cls, device_type_value: str):
        normalized_value = str(device_type_value or "").strip()
        if not normalized_value:
            return []

        variants = []
        for value in (
            normalized_value,
            cls.normalize_device_type_value(normalized_value),
            cls.resolve_device_type_alias(normalized_value),
        ):
            value = str(value or "").strip()
            if value and value not in variants:
                variants.append(value)
        return variants

    @property
    def device_type_alias(self) -> str:
        return self.resolve_device_type_alias(self.device_type)

    def get_device_type_display(self):
        return self.normalize_device_type_value(self.device_type) or self.device_type

    def save(self, *args, **kwargs):
        original_vendor = getattr(self, "vendor", "")
        normalized_vendor = self.normalize_vendor_value(original_vendor)
        self.vendor = normalized_vendor
        original_device_type = getattr(self, "device_type", "")
        normalized_device_type = self.normalize_device_type_value(original_device_type)
        self.device_type = normalized_device_type
        update_fields = kwargs.get("update_fields")
        if update_fields is not None and normalized_vendor != original_vendor and "vendor" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["vendor"]
            update_fields = kwargs["update_fields"]
        if update_fields is not None and normalized_device_type != original_device_type and "device_type" not in update_fields:
            kwargs["update_fields"] = list(update_fields) + ["device_type"]
        super().save(*args, **kwargs)


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
    collection_type = models.CharField(max_length=32, default='arp', verbose_name='采集类型')
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

        vendor = DeviceCollectionPlans.resolve_vendor_alias(self.summary_plan.vendor)
        device_type = DeviceCollectionPlans.resolve_device_type_alias(self.summary_plan.device_type)
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

    def save(self, *args, **kwargs):
        if self.collect_method not in {"get", "get_config"}:
            raise ValueError("NETCONF 模板 collect_method 仅支持 get / get_config")
        super().save(*args, **kwargs)


class PlansToDevice(models.Model):
    """方案与设备关联：支持本地采集或南向驱动采集，二选一，默认本地采集。"""
    BINDING_SOURCE_AUTO = "auto"
    BINDING_SOURCE_MANUAL = "manual"
    BINDING_SOURCE_LEGACY = "legacy_bridge"
    BINDING_SOURCE_CHOICES = [
        (BINDING_SOURCE_AUTO, "自动绑定"),
        (BINDING_SOURCE_MANUAL, "手工绑定"),
        (BINDING_SOURCE_LEGACY, "旧链路桥接"),
    ]

    device_serial_num = models.CharField(
        verbose_name="设备序列号",
        max_length=200,
        blank=True,
        default="",
    )
    manage_ip = models.CharField(verbose_name="设备IP", max_length=100, null=False, blank=False)
    plan = models.ForeignKey("DeviceCollectionPlans", on_delete=models.SET_NULL, null=True, related_name="device_plan",
                             verbose_name="关联方案")
    profile_code = models.CharField(max_length=64, blank=True, default="", verbose_name="画像编码")
    binding_source = models.CharField(
        max_length=20,
        choices=BINDING_SOURCE_CHOICES,
        default=BINDING_SOURCE_MANUAL,
        verbose_name="绑定来源",
    )
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
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
    last_bound_at = models.DateTimeField(null=True, blank=True, verbose_name="最近绑定时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        verbose_name = '采集方案关系表'
        verbose_name_plural = '采集方案关系表'
        db_table = 'device_api_plan2device'
        ordering = ['manage_ip', 'created_at']
        constraints = [
            models.UniqueConstraint(
                fields=["device_serial_num", "plan"],
                name="uniq_device_api_plan_binding",
            )
        ]
        indexes = [
            models.Index(fields=["device_serial_num", "is_active"]),
            models.Index(fields=["manage_ip", "profile_code"]),
        ]

    def __str__(self):
        plan_name = self.plan.name if self.plan else ""
        return f"{self.device_serial_num or self.manage_ip} ({plan_name})"


class DeviceCollectionRule(models.Model):
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
    legacy_rule_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="legacy规则ID")

    @staticmethod
    def is_valid_xml(xml_string):
        try:
            ET.fromstring(xml_string)
            return True
        except ET.ParseError:
            return False

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.method == 'CLI':
            if not isinstance(self.execute, str):
                raise ValueError("命令校验失败，CLI校验内容不是标准命令行.")
        elif self.method == 'NETCONF':
            if not self.is_valid_xml(self.execute):
                raise ValueError("命令校验失败，NETCONF校验内容不符合XML规范.")
        elif self.method == 'REST_API':
            if not isinstance(json.loads(self.execute), dict):
                raise ValueError("命令校验失败，REST_API校验内容不是dict类型.")
        super(DeviceCollectionRule, self).save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    class Meta:
        verbose_name = "采集规则"
        verbose_name_plural = "采集规则"
        db_table = "device_api_collection_rule"
        indexes = [models.Index(fields=["id"])]


class DeviceCollectionMatchRule(models.Model):
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
    name = models.CharField(verbose_name='规则名', max_length=10, blank=True)
    fields = models.CharField(verbose_name='匹配字段', max_length=50, default='', blank=True, null=True)
    operator = models.CharField(verbose_name='操作符', choices=OPER_CHOICES, max_length=50, null=True, default='__exact', blank=True)
    value = models.CharField(verbose_name='匹配值', max_length=50, default='', blank=True, null=True)
    legacy_match_rule_id = models.IntegerField(null=True, blank=True, db_index=True, verbose_name="legacy匹配规则ID")
    rule = models.ForeignKey(
        "device_api.DeviceCollectionRule",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='match_rule',
    )

    def __str__(self):
        operator_name = dict(self.OPER_CHOICES).get(self.operator, '')
        return "{}-{}-{}-{}".format(self.name, self.fields, operator_name, self.value)

    class Meta:
        verbose_name = "采集规则匹配项"
        verbose_name_plural = "采集规则匹配项"
        db_table = "device_api_collection_match_rule"
        indexes = [models.Index(fields=["id"])]
        unique_together = (("rule", "name"),)


@receiver(pre_save, sender=DeviceCollectionMatchRule)
def auto_device_match_rule_name(sender, instance, **kwargs):
    if not instance.name:
        last_instance = (
            sender.objects.select_related('rule')
            .filter(rule=instance.rule)
            .order_by('-id')
            .first()
        )
        if last_instance:
            last_id = ord(last_instance.name)
            instance.name = chr(last_id + 1)
        else:
            instance.name = 'A'
