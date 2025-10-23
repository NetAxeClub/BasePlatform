import json
import logging
import pytz
from datetime import datetime
from rest_framework import serializers
from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan, NetconfXMLTemplate


class DeviceSummaryPlansSerializer(serializers.ModelSerializer):
    """采集汇总方案序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)
    collect_plans_count = serializers.SerializerMethodField()
    collect_plans = serializers.SerializerMethodField()

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            'id', 'name', 'vendor', 'vendor_display', 'device_type',
            'description', 'is_active', 'collect_plans_count', 'collect_plans', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor_display',
                           'collect_plans_count', 'created_at', 'updated_at']

    def get_collect_plans_count(self, obj):
        return obj.collect_plans.count()

    def get_collect_plans(self, obj):
        collect_plans = obj.collect_plans.all()[:5]
        return DeviceCollectionPlanSerializer(collect_plans, many=True).data


class DeviceSummaryPlansCreateSerializer(serializers.ModelSerializer):
    """采集汇总方案创建序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            'id', 'name', 'vendor', 'vendor_display', 'device_type',
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor_display', 'created_at', 'updated_at']

    def validate_name(self, value):
        if DeviceCollectionPlans.objects.filter(name=value).exists():
            raise serializers.ValidationError("采集汇总方案名称已存在")
        return value


class DeviceSummaryPlansUpdateSerializer(serializers.ModelSerializer):
    """采集汇总方案更新序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            'id', 'name', 'vendor', 'vendor_display', 'device_type',
            'description', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor_display', 'created_at', 'updated_at']

    def validate_name(self, value):
        instance = self.instance
        if instance and DeviceCollectionPlans.objects.filter(name=value).exclude(id=instance.id).exists():
            raise serializers.ValidationError("采集汇总方案名称已存在")
        return value


class DeviceSummaryPlansDetailSerializer(serializers.ModelSerializer):
    """采集汇总方案详情序列化器"""
    vendor_display = serializers.CharField(source='get_vendor_display', read_only=True)
    collect_plans = serializers.SerializerMethodField()

    def get_collect_plans(self, obj):
        collect_plans = obj.collect_plans.all()
        return DeviceCollectionPlanSerializer(collect_plans, many=True).data

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            'id', 'name', 'vendor', 'vendor_display', 'device_type',
            'description', 'is_active', 'collect_plans', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vendor_display', 'created_at', 'updated_at']


class DeviceCollectionPlanSerializer(serializers.ModelSerializer):
    """设备采集方案序列化器"""
    summary_plan_name = serializers.CharField(source='summary_plan.name', read_only=True)
    summary_plan_vendor = serializers.CharField(source='summary_plan.vendor', read_only=True)
    summary_plan_vendor_display = serializers.CharField(source='summary_plan.get_vendor_display', read_only=True)
    summary_plan_device_type = serializers.CharField(source='summary_plan.device_type', read_only=True)
    description = serializers.CharField()
    xml_templates = serializers.SerializerMethodField()

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            'id', 'summary_plan', 'summary_plan_name', 'summary_plan_vendor', 'summary_plan_vendor_display',
            'summary_plan_device_type', 'name', 'description', 'type', 'machine_room_ip',
            'textfsm_enabled', 'textfsm_template',
            'netmiko_enabled', 'netmiko_path', 'netmiko_method', 'netmiko_field_mappings',
            'netconf_enabled', 'netconf_path', 'netconf_method', 'netconf_field_mappings',
            'data_processor_enabled', 'data_processor', 'is_active', 'xml_templates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'summary_plan_name', 'summary_plan_vendor', 'summary_plan_vendor_display',
                            'summary_plan_device_type', 'created_at', 'updated_at']

    def get_xml_templates(self, obj):
        """获取XML模板列表"""
        try:
            if hasattr(obj, 'xml_templates'):
                if hasattr(obj.xml_templates, 'all'):
                    templates = obj.xml_templates.all()
                    if templates.exists():
                        return NetconfXMLTemplateSerializer(templates, many=True).data
                    else:
                        return []
                else:
                    return NetconfXMLTemplateSerializer(obj.xml_templates, many=True).data
            return []
        except Exception as e:
            logging.warning(f"获取XML模板失败: {str(e)}")
            return []


class DeviceCollectionPlanCreateSerializer(serializers.ModelSerializer):
    """设备采集方案创建序列化器"""
    summary_plan_id = serializers.IntegerField(
        write_only=True,
        help_text='汇总方案ID'
    )
    summary_plan_name = serializers.CharField(source='summary_plan.name', read_only=True)
    summary_plan_vendor = serializers.CharField(source='summary_plan.vendor', read_only=True)
    summary_plan_device_type = serializers.CharField(source='summary_plan.device_type', read_only=True)
    xml_templates = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text='NETCONF XML模板列表'
    )

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            'id', 'summary_plan_id', 'summary_plan', 'summary_plan_name', 'summary_plan_vendor',
            'summary_plan_device_type', 'name', 'description', 'type', 'machine_room_ip',
            'textfsm_enabled', 'textfsm_template',
            'netmiko_enabled', 'netmiko_path', 'netmiko_method', 'netmiko_field_mappings',
            'netconf_enabled', 'netconf_path', 'netconf_method', 'netconf_field_mappings',
            'data_processor_enabled', 'data_processor', 'is_active', 'xml_templates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'summary_plan', 'summary_plan_name', 'summary_plan_vendor',
                            'summary_plan_device_type', 'created_at', 'updated_at']

    def validate(self, data):
        # 验证至少选择一种采集方式
        if not data.get('netconf_enabled') and not data.get('netmiko_enabled'):
            raise serializers.ValidationError("至少需要启用一种采集方式（NETCONF或Netmiko）")

        # 验证Netmiko相关配置
        if data.get('netmiko_enabled'):
            # 如果启用Netmiko，建议提供textfsm_template（但不是强制的）
            if not data.get('textfsm_template'):
                # 只是警告，不阻止创建
                pass

            # 如果提供了netmiko_field_mappings，验证JSON格式
            netmiko_mappings = data.get('netmiko_field_mappings')
            if netmiko_mappings:
                try:
                    if isinstance(netmiko_mappings, str):
                        json.loads(netmiko_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError("netmiko_field_mappings必须是有效的JSON格式")

        # 验证NETCONF相关配置
        if data.get('netconf_enabled'):
            # 如果启用NETCONF，必须提供XML模板
            xml_templates = data.get('xml_templates', [])
            if not xml_templates:
                raise serializers.ValidationError("启用NETCONF时必须提供XML模板")

            # 验证XML模板数据的完整性
            for i, template in enumerate(xml_templates):
                required_fields = ['name', 'xml_template']
                for field in required_fields:
                    if not template.get(field):
                        raise serializers.ValidationError(f"XML模板 {i + 1} 缺少必需字段: {field}")

            # 如果提供了netconf_field_mappings，验证JSON格式
            netconf_mappings = data.get('netconf_field_mappings')
            if netconf_mappings:
                try:
                    if isinstance(netconf_mappings, str):
                        json.loads(netconf_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError("netconf_field_mappings必须是有效的JSON格式")

        return data

    def create(self, validated_data):
        from django.db import transaction
        from apps.device_api.models import DeviceCollectionPlans

        # 处理summary_plan_id
        summary_plan_id = validated_data.pop('summary_plan_id', None)
        if summary_plan_id:
            try:
                summary_plan = DeviceCollectionPlans.objects.get(id=summary_plan_id)
                validated_data['summary_plan'] = summary_plan
            except DeviceCollectionPlans.DoesNotExist:
                raise serializers.ValidationError(f"汇总方案ID {summary_plan_id} 不存在")
        else:
            raise serializers.ValidationError("必须提供summary_plan_id")

        xml_templates_data = validated_data.pop('xml_templates', [])

        try:
            with transaction.atomic():
                # 创建采集方案
                collection_plan = DeviceSubCollectionPlan.objects.create(**validated_data)

                # 如果启用了NETCONF且有XML模板，创建XML模板
                if collection_plan.netconf_enabled and xml_templates_data:
                    for template_data in xml_templates_data:
                        NetconfXMLTemplate.objects.create(
                            collection_plan=collection_plan,
                            **template_data
                        )

                return collection_plan

        except Exception as e:
            raise serializers.ValidationError(f"创建失败: {str(e)}")


class DeviceCollectionPlanUpdateSerializer(serializers.ModelSerializer):
    """设备采集方案更新序列化器"""
    summary_plan_id = serializers.IntegerField(
        write_only=True,
        required=False,
        help_text='汇总方案ID（可选，用于更换汇总方案）'
    )
    xml_templates = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        help_text='NETCONF XML模板列表'
    )

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            'id', 'summary_plan_id', 'name', 'description', 'type', 'machine_room_ip',
            'textfsm_enabled', 'textfsm_template',
            'netmiko_enabled', 'netmiko_path', 'netmiko_method', 'netmiko_field_mappings',
            'netconf_enabled', 'netconf_path', 'netconf_method', 'netconf_field_mappings',
            'data_processor_enabled', 'data_processor', 'is_active', 'xml_templates',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        # 在更新时，如果字段没有传入，从实例中获取现有值
        if self.instance:
            netmiko_enabled = data.get('netmiko_enabled', self.instance.netmiko_enabled)
            netconf_enabled = data.get('netconf_enabled', self.instance.netconf_enabled)
        else:
            netmiko_enabled = data.get('netmiko_enabled', False)
            netconf_enabled = data.get('netconf_enabled', False)

        # 验证至少选择一种采集方式
        if not netconf_enabled and not netmiko_enabled:
            raise serializers.ValidationError("至少需要启用一种采集方式（NETCONF或Netmiko）")

        # 验证Netmiko相关配置
        if netmiko_enabled:
            # 如果提供了netmiko_field_mappings，验证JSON格式
            netmiko_mappings = data.get('netmiko_field_mappings')
            if netmiko_mappings:
                try:
                    if isinstance(netmiko_mappings, str):
                        json.loads(netmiko_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError("netmiko_field_mappings必须是有效的JSON格式")

        # 验证NETCONF相关配置
        if netconf_enabled:
            # 如果启用NETCONF，必须提供XML模板
            xml_templates = data.get('xml_templates', [])
            if not xml_templates:
                raise serializers.ValidationError("启用NETCONF时必须提供XML模板")

            # 验证XML模板数据的完整性
            for i, template in enumerate(xml_templates):
                if not template.get('name'):
                    raise serializers.ValidationError(f"XML模板[{i}]必须包含名称")
                if not template.get('xml_template'):
                    raise serializers.ValidationError(f"XML模板[{i}]必须包含XML内容")

            # 如果提供了netconf_field_mappings，验证JSON格式
            netconf_mappings = data.get('netconf_field_mappings')
            if netconf_mappings:
                try:
                    if isinstance(netconf_mappings, str):
                        json.loads(netconf_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError("netconf_field_mappings必须是有效的JSON格式")

        return data

    def to_representation(self, instance):
        """重写to_representation方法，确保xml_templates字段能正确序列化"""
        # 先处理xml_templates字段，避免在super()调用时出错
        xml_templates_data = []
        try:
            if hasattr(instance, 'xml_templates'):
                # 如果是RelatedManager，调用all()方法获取查询集
                if hasattr(instance.xml_templates, 'all'):
                    templates = instance.xml_templates.all()
                    if templates.exists():
                        xml_templates_data = NetconfXMLTemplateSerializer(templates, many=True).data
                    else:
                        xml_templates_data = []
                else:
                    # 如果已经是列表或其他类型
                    xml_templates_data = NetconfXMLTemplateSerializer(instance.xml_templates, many=True).data
            else:
                xml_templates_data = []
        except Exception as e:
            # 如果出现任何错误，返回空列表
            xml_templates_data = []

        # 创建一个临时的数据字典，不包含xml_templates字段
        temp_data = {}
        for field_name in self.fields:
            if field_name != 'xml_templates':
                try:
                    field = self.fields[field_name]
                    if hasattr(instance, field_name):
                        value = getattr(instance, field_name)
                        if hasattr(field, 'to_representation'):
                            temp_data[field_name] = field.to_representation(value)
                        else:
                            temp_data[field_name] = value
                    else:
                        temp_data[field_name] = None
                except Exception:
                    temp_data[field_name] = None

        # 手动设置xml_templates字段
        temp_data['xml_templates'] = xml_templates_data

        return temp_data

    def update(self, instance, validated_data):
        from django.db import transaction
        from apps.device_api.models import DeviceCollectionPlans

        # 处理summary_plan_id
        summary_plan_id = validated_data.pop('summary_plan_id', None)
        if summary_plan_id:
            try:
                summary_plan = DeviceCollectionPlans.objects.get(id=summary_plan_id)
                validated_data['summary_plan'] = summary_plan
            except DeviceCollectionPlans.DoesNotExist:
                raise serializers.ValidationError(f"汇总方案ID {summary_plan_id} 不存在")

        xml_templates_data = validated_data.pop('xml_templates', None)

        try:
            with transaction.atomic():
                # 处理字段映射的默认值
                if 'netmiko_field_mappings' in validated_data and not validated_data['netmiko_field_mappings']:
                    validated_data['netmiko_field_mappings'] = {}
                if 'netconf_field_mappings' in validated_data and not validated_data['netconf_field_mappings']:
                    validated_data['netconf_field_mappings'] = {}

                # 更新采集方案
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.save()

                # 处理XML模板
                if xml_templates_data is not None:  # 只有当明确传入xml_templates时才处理
                    if instance.netconf_enabled and xml_templates_data:
                        # 智能更新XML模板：根据ID查找修改，新增不存在的，删除多余的
                        self._update_xml_templates(instance, xml_templates_data)
                    elif not instance.netconf_enabled:
                        # 如果禁用了NETCONF，删除所有XML模板
                        instance.xml_templates.all().delete()

                return instance

        except Exception as e:
            raise serializers.ValidationError(f"更新失败: {str(e)}")

    def _update_xml_templates(self, instance, new_templates_data):
        """智能更新XML模板：根据ID查找修改，新增不存在的，删除多余的"""
        from .models import NetconfXMLTemplate

        try:
            # 获取现有模板的ID映射
            existing_templates = {
                template.id: template
                for template in instance.xml_templates.all()
            }

            # 用于跟踪已处理的模板ID
            processed_template_ids = set()

            for template_data in new_templates_data:
                template_id = template_data.get('id')

                if template_id and template_id in existing_templates:
                    # 更新现有模板
                    existing_template = existing_templates[template_id]
                    for attr, value in template_data.items():
                        if attr != 'id':  # 不更新ID字段
                            setattr(existing_template, attr, value)
                    existing_template.save()
                    processed_template_ids.add(template_id)
                else:
                    # 创建新模板
                    NetconfXMLTemplate.objects.create(
                        collection_plan=instance,
                        **template_data
                    )

            # 删除未处理的现有模板（即多余的模板）
            templates_to_delete = [
                template_id for template_id in existing_templates.keys()
                if template_id not in processed_template_ids
            ]

            if templates_to_delete:
                NetconfXMLTemplate.objects.filter(id__in=templates_to_delete).delete()

        except Exception as e:
            # 记录错误但不阻止整个更新操作
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"更新XML模板失败: {str(e)}")
            # 可以选择重新抛出异常或继续执行
            raise serializers.ValidationError(f"更新XML模板失败: {str(e)}")


class NetconfXMLTemplateSerializer(serializers.ModelSerializer):
    """NETCONF XML模板序列化器"""

    class Meta:
        model = NetconfXMLTemplate
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']


class NetconfXMLTemplateListSerializer(serializers.ModelSerializer):
    """NETCONF XML模板列表序列化器"""
    collection_plan_name = serializers.CharField(source='collection_plan.name', read_only=True)
    summary_plan_name = serializers.CharField(source='collection_plan.summary_plan.name', read_only=True)
    summary_plan_vendor = serializers.CharField(source='collection_plan.summary_plan.vendor', read_only=True)
    summary_plan_device_type = serializers.CharField(source='collection_plan.summary_plan.device_type', read_only=True)
    
    class Meta:
        model = NetconfXMLTemplate
        fields = [
            'id', 'name', 'description', 'is_active',
            'collection_plan_name', 'summary_plan_name', 'summary_plan_vendor', 'summary_plan_device_type',
            'created_at', 'updated_at'
        ]


class CollectionFilterSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(help_text='采集方案ID', required=False)
    plan_name = serializers.CharField(help_text='采集方案名称', required=False)
    device_ip = serializers.CharField(help_text='设备IP地址', required=False)
    device_name = serializers.CharField(help_text='设备名称', required=False, allow_blank=True)
    device_type = serializers.CharField(help_text='设备类型', required=False)
    vendor = serializers.CharField(help_text='厂商', required=False, allow_blank=True)
    collection_method = serializers.CharField(help_text='采集方式', required=False)
    method_name = serializers.CharField(help_text='采集方法名称', required=False, allow_blank=True)
    status = serializers.CharField(help_text='采集状态', required=False)
    start_date = serializers.CharField(help_text='开始采集时间', required=False)
    end_date = serializers.CharField(help_text='结束采集日期', required=False)
    start_time = serializers.CharField(help_text='开始采集时间', required=False)
    end_time = serializers.CharField(help_text='结束采集时间', required=False)
    days = serializers.IntegerField(help_text='最近天数', required=False)
    page = serializers.IntegerField(help_text='页码', required=False, default=1)
    page_size = serializers.IntegerField(help_text='每页大小', required=False, default=10)
    sort_by = serializers.CharField(help_text='排序字段', required=False, default='collected_at')
    sort_order = serializers.CharField(help_text='排序方向', required=False, default='desc')


class CollectionResultListSerializer(serializers.Serializer):
    """采集结果列表序列化器"""
    _id = serializers.CharField(read_only=True, help_text='MongoDB文档ID')
    plan_id = serializers.IntegerField(help_text='采集方案ID')
    plan_name = serializers.CharField(help_text='采集方案名称')
    device_ip = serializers.CharField(help_text='设备IP地址')
    device_name = serializers.CharField(help_text='设备名称')
    idc_name = serializers.CharField(help_text='机房名称')
    device_type = serializers.CharField(help_text='设备类型')
    vendor = serializers.CharField(help_text='厂商')
    collection_method = serializers.CharField(help_text='采集方式')
    method_name = serializers.CharField(help_text='采集方法名称')
    collected_at = serializers.SerializerMethodField(help_text='采集时间')
    status = serializers.CharField(help_text='采集状态')

    @staticmethod
    def get_collected_at(obj):
        """格式化采集时间为标准格式"""

        collected_at = obj.get('collected_at')
        if not collected_at:
            return None
            
        try:
            # 如果是字符串格式，先解析为datetime对象
            if isinstance(collected_at, str):
                # 处理ISO 8601格式
                if 'T' in collected_at and '+' in collected_at:
                    # 移除时区信息，只保留本地时间
                    dt = datetime.fromisoformat(collected_at.replace('Z', '+00:00'))
                    # 转换为本地时间（这里假设是北京时间）
                    local_tz = pytz.timezone('Asia/Shanghai')
                    dt = dt.astimezone(local_tz)
                else:
                    dt = datetime.fromisoformat(collected_at)
            else:
                # 如果已经是datetime对象
                dt = collected_at
                
            # 格式化为标准格式：YYYY-MM-DD HH:MM:SS
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            # 如果解析失败，返回原始值
            return str(collected_at)


class CollectionResultDetailSerializer(CollectionResultListSerializer):
    """采集结果详情序列化器"""
    data = serializers.JSONField(help_text='原始数据')
    processed_data = serializers.JSONField(help_text='处理后数据')

