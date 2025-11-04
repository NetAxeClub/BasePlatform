import json
from django.db import models


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
        ('Centec', '盛科'),
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

    # 采集方式配置,Netmiko配置
    netmiko_enabled = models.BooleanField(default=True, verbose_name='启用Netmiko')
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

    def _process_with_exec(self, enabled: bool, code: str, data):
        """通用的基于 exec 的数据处理执行器"""
        if not enabled or not code:
            return data

        try:
            # 创建安全的执行环境
            local_vars = {
                'data': data,
            }

            # 执行数据处理代码
            exec(code, globals(), local_vars)

            # 检查函数是否定义成功，并调用它
            if 'process_data' in local_vars:
                processed_result = local_vars['process_data'](local_vars['data'])
            else:
                raise RuntimeError("在执行代码后未找到 'process_data' 函数。")

            # 获取处理结果
            if processed_result is not None:
                return processed_result

            # 如果没有明确的返回值，返回处理后的数据
            return data

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"执行数据处理代码失败: {str(e)}")
            return data

    def process_netmiko_data(self, data):
        """处理采集到的数据"""
        return self._process_with_exec(self.netmiko_processor_enabled, self.netmiko_processor, data)

    def process_netconf_data(self, data):
        """处理采集到的数据"""
        return self._process_with_exec(self.netconf_processor_enabled, self.netconf_processor, data)

    def save(self, *args, **kwargs):
        """保存时确保字段映射有正确的默认值"""
        # 确保字段映射字段有默认值
        if not self.netmiko_field_mappings:
            self.netmiko_field_mappings = {}
        if not self.netconf_field_mappings:
            self.netconf_field_mappings = {}

        super().save(*args, **kwargs)


class NetconfXMLTemplate(models.Model):
    """NETCONF XML模板模型"""
    COLLECT_METHOD_CHOICES = [
        ('get', 'GET'),
        ('get_bulk', 'GET_BULK'),
        ('rpc', 'RPC'),
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

