import json
import logging
import pytz
from datetime import datetime
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from apps.asset.models import NetworkDevice
from apps.device_api.fields_mapping import DEFAULT_COLLECTION_TYPES
from apps.device_api.models import (
    DeviceCollectionMatchRule,
    DeviceCollectionRule,
    DeviceCollectionPlans,
    DeviceDiscoveryState,
    DeviceSubCollectionPlan,
    NetconfXMLTemplate,
    PlansToDevice,
    PlatformProfile,
)
from apps.device_api.platform_profiles import PlatformProfileService
from apps.device_api.services_new import DeviceCollectionService


def _normalize_enabled_collection_types(value):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise serializers.ValidationError("enabled_collection_types 必须为数组")

    normalized_types = []
    invalid_types = []
    for collection_type in value:
        type_name = str(collection_type).strip()
        if not type_name:
            continue
        if type_name not in DEFAULT_COLLECTION_TYPES:
            invalid_types.append(type_name)
            continue
        if type_name not in normalized_types:
            normalized_types.append(type_name)

    if invalid_types:
        raise serializers.ValidationError(
            f"enabled_collection_types 包含未支持的采集类型: {', '.join(invalid_types)}"
        )
    return normalized_types


class DeviceCollectionPlansSerializer(serializers.ModelSerializer):
    """采集汇总方案序列化器"""

    vendor_display = serializers.CharField(source="get_vendor_display", read_only=True)
    collect_plans_count = serializers.SerializerMethodField()
    collect_plans = serializers.SerializerMethodField()

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            "id",
            "name",
            "vendor",
            "vendor_display",
            "device_type",
            "description",
            "profile_code",
            "plan_kind",
            "generated_by_system",
            "version",
            "is_default",
            "enabled_collection_types",
            "collection_method",
            "is_active",
            "collect_plans_count",
            "collect_plans",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor_display",
            "collect_plans_count",
            "generated_by_system",
            "created_at",
            "updated_at",
        ]

    def get_collect_plans_count(self, obj):
        return obj.collect_plans.count()

    def get_collect_plans(self, obj):
        collect_plans = obj.collect_plans.all()[:5]
        return DeviceSubCollectionPlanSerializer(collect_plans, many=True).data


class DeviceCollectionPlansCreateSerializer(serializers.ModelSerializer):
    """采集汇总方案创建序列化器。

    创建空白方案时会自动为该方案创建所有采集类型的空白子方案（仅名称与采集类型确定）。
    """

    vendor_display = serializers.CharField(source="get_vendor_display", read_only=True)

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            "id",
            "name",
            "vendor",
            "vendor_display",
            "device_type",
            "description",
            "profile_code",
            "plan_kind",
            "generated_by_system",
            "version",
            "is_default",
            "enabled_collection_types",
            "collection_method",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "vendor_display",
            "generated_by_system",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        if DeviceCollectionPlans.objects.filter(name=value).exists():
            raise serializers.ValidationError("采集汇总方案名称已存在")
        return value

    def validate_enabled_collection_types(self, value):
        return _normalize_enabled_collection_types(value)

    def create(self, validated_data):
        with transaction.atomic():
            validated_data.setdefault("plan_kind", DeviceCollectionPlans.PLAN_KIND_RUNTIME)
            validated_data.setdefault("version", 1)
            summary_plan = DeviceCollectionPlans.objects.create(**validated_data)
            DeviceCollectionService.sync_summary_plan_sub_plans(summary_plan)
            if summary_plan.profile_code:
                profile = PlatformProfile.objects.filter(code=summary_plan.profile_code).first()
                if profile:
                    PlatformProfileService.apply_profile_defaults(summary_plan, profile)
            return summary_plan


class DeviceCollectionPlansUpdateSerializer(serializers.ModelSerializer):
    """采集汇总方案更新序列化器"""

    vendor_display = serializers.CharField(source="get_vendor_display", read_only=True)

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            "id",
            "name",
            "vendor",
            "vendor_display",
            "device_type",
            "description",
            "profile_code",
            "plan_kind",
            "generated_by_system",
            "version",
            "is_default",
            "enabled_collection_types",
            "collection_method",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "vendor_display", "generated_by_system", "created_at", "updated_at"]

    def validate_name(self, value):
        instance = self.instance
        if (
            instance
            and DeviceCollectionPlans.objects.filter(name=value)
            .exclude(id=instance.id)
            .exists()
        ):
            raise serializers.ValidationError("采集汇总方案名称已存在")
        return value

    def validate_enabled_collection_types(self, value):
        return _normalize_enabled_collection_types(value)

    def update(self, instance, validated_data):
        with transaction.atomic():
            summary_plan = super().update(instance, validated_data)
            DeviceCollectionService.sync_summary_plan_sub_plans(summary_plan)
            return summary_plan


class DeviceCollectionPlansDetailSerializer(serializers.ModelSerializer):
    """采集汇总方案详情序列化器"""

    vendor_display = serializers.CharField(source="get_vendor_display", read_only=True)
    collect_plans = serializers.SerializerMethodField()

    def get_collect_plans(self, obj):
        collect_plans = obj.collect_plans.all()
        return DeviceSubCollectionPlanSerializer(collect_plans, many=True).data

    class Meta:
        model = DeviceCollectionPlans
        fields = [
            "id",
            "name",
            "vendor",
            "vendor_display",
            "device_type",
            "description",
            "profile_code",
            "plan_kind",
            "generated_by_system",
            "version",
            "is_default",
            "enabled_collection_types",
            "collection_method",
            "is_active",
            "collect_plans",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "vendor_display", "generated_by_system", "created_at", "updated_at"]


class PlatformProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlatformProfile
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class DeviceCollectionMatchRuleSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="get_operator_display", read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.select_related("rule")

    class Meta:
        model = DeviceCollectionMatchRule
        fields = "__all__"
        read_only_fields = ["legacy_match_rule_id"]


class DeviceCollectionRuleSerializer(serializers.ModelSerializer):
    match_rule = DeviceCollectionMatchRuleSerializer(many=True, read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.prefetch_related("match_rule")

    class Meta:
        model = DeviceCollectionRule
        fields = "__all__"
        read_only_fields = ["legacy_rule_id"]


class DeviceSubCollectionPlanSerializer(serializers.ModelSerializer):
    """设备采集方案序列化器"""

    summary_plan_name = serializers.CharField(
        source="summary_plan.name", read_only=True
    )
    summary_plan_vendor = serializers.CharField(
        source="summary_plan.vendor", read_only=True
    )
    summary_plan_vendor_display = serializers.CharField(
        source="summary_plan.get_vendor_display", read_only=True
    )
    summary_plan_device_type = serializers.CharField(
        source="summary_plan.device_type", read_only=True
    )
    description = serializers.CharField()
    xml_templates = serializers.SerializerMethodField()

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            "id",
            "summary_plan",
            "summary_plan_name",
            "summary_plan_vendor",
            "summary_plan_vendor_display",
            "summary_plan_device_type",
            "name",
            "description",
            "collection_type",
            "textfsm_template",
            "netmiko_enabled",
            "netmiko_path",
            "netmiko_method",
            "netmiko_field_mappings",
            "netmiko_processor_enabled",
            "netmiko_processor",
            "netconf_enabled",
            "netconf_path",
            "netconf_field_mappings",
            "netconf_processor_enabled",
            "netconf_processor",
            "snmp_enabled",
            "snmp_version",
            "snmp_oids",
            "snmp_path",
            "snmp_field_mappings",
            "snmp_processor_enabled",
            "snmp_processor",
            "restconf_enabled",
            "restconf_endpoint",
            "restconf_method",
            "restconf_path",
            "restconf_field_mappings",
            "restconf_processor_enabled",
            "restconf_processor",
            "telemetry_enabled",
            "telemetry_subscription_path",
            "telemetry_sampling_interval",
            "telemetry_data_format",
            "telemetry_path",
            "telemetry_field_mappings",
            "telemetry_processor_enabled",
            "telemetry_processor",
            "xml_templates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "summary_plan_name",
            "summary_plan_vendor",
            "summary_plan_vendor_display",
            "summary_plan_device_type",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "netmiko_processor": {"write_only": True},
            "netconf_processor": {"write_only": True},
            "snmp_processor": {"write_only": True},
            "restconf_processor": {"write_only": True},
            "telemetry_processor": {"write_only": True},
        }

    def get_xml_templates(self, obj):
        """获取XML模板列表"""
        try:
            if hasattr(obj, "xml_templates"):
                if hasattr(obj.xml_templates, "all"):
                    templates = obj.xml_templates.all()
                    if templates.exists():
                        return NetconfXMLTemplateSerializer(templates, many=True).data
                    else:
                        return []
                else:
                    return NetconfXMLTemplateSerializer(
                        obj.xml_templates, many=True
                    ).data
            return []
        except Exception as e:
            logging.warning(f"获取XML模板失败: {str(e)}")
            return []


class DeviceSubCollectionPlanCreateSerializer(serializers.ModelSerializer):
    """设备采集方案创建序列化器。

    处理器相关字段为可选：未传或传 false/空 时按「未启用」处理，仅使用字段映射。
    """

    summary_plan_id = serializers.IntegerField(write_only=True, help_text="汇总方案ID")
    summary_plan_name = serializers.CharField(
        source="summary_plan.name", read_only=True
    )
    summary_plan_vendor = serializers.CharField(
        source="summary_plan.vendor", read_only=True
    )
    summary_plan_device_type = serializers.CharField(
        source="summary_plan.device_type", read_only=True
    )
    xml_templates = serializers.ListField(
        child=serializers.DictField(), required=False, help_text="NETCONF XML模板列表"
    )

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            "id",
            "summary_plan_id",
            "summary_plan",
            "summary_plan_name",
            "summary_plan_vendor",
            "summary_plan_device_type",
            "name",
            "description",
            "collection_type",
            "textfsm_template",
            "netmiko_enabled",
            "netmiko_path",
            "netmiko_method",
            "netmiko_field_mappings",
            "netmiko_processor_enabled",
            "netmiko_processor",
            "netconf_enabled",
            "netconf_path",
            "netconf_field_mappings",
            "netconf_processor_enabled",
            "netconf_processor",
            "snmp_enabled",
            "snmp_version",
            "snmp_oids",
            "snmp_path",
            "snmp_field_mappings",
            "snmp_processor_enabled",
            "snmp_processor",
            "restconf_enabled",
            "restconf_endpoint",
            "restconf_method",
            "restconf_path",
            "restconf_field_mappings",
            "restconf_processor_enabled",
            "restconf_processor",
            "telemetry_enabled",
            "telemetry_subscription_path",
            "telemetry_sampling_interval",
            "telemetry_data_format",
            "telemetry_path",
            "telemetry_field_mappings",
            "telemetry_processor_enabled",
            "telemetry_processor",
            "xml_templates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "summary_plan",
            "summary_plan_name",
            "summary_plan_vendor",
            "summary_plan_device_type",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "netmiko_processor_enabled": {"required": False, "default": False},
            "netmiko_processor": {"required": False, "allow_blank": True, "default": ""},
            "netconf_processor_enabled": {"required": False, "default": False},
            "netconf_processor": {"required": False, "allow_blank": True, "default": ""},
            "snmp_processor_enabled": {"required": False, "default": False},
            "snmp_processor": {"required": False, "allow_blank": True, "default": ""},
            "restconf_processor_enabled": {"required": False, "default": False},
            "restconf_processor": {"required": False, "allow_blank": True, "default": ""},
            "telemetry_processor_enabled": {"required": False, "default": False},
            "telemetry_processor": {"required": False, "allow_blank": True, "default": ""},
        }

    def validate(self, data):
        enabled_methods = [
            key for key in (
                "netmiko_enabled",
                "netconf_enabled",
                "snmp_enabled",
                "restconf_enabled",
                "telemetry_enabled",
            )
            if data.get(key)
        ]

        # 验证至少选择一种采集方式
        if not enabled_methods:
            raise serializers.ValidationError(
                "至少需要启用一种采集方式（NETCONF、Netmiko、SNMP、RESTCONF 或 Telemetry）"
            )

        # 验证Netmiko相关配置
        if data.get("netmiko_enabled"):
            # 如果启用Netmiko，建议提供textfsm_template（但不是强制的）
            if not data.get("textfsm_template"):
                # 只是警告，不阻止创建
                pass

            # 如果提供了netmiko_field_mappings，验证JSON格式
            netmiko_mappings = data.get("netmiko_field_mappings")
            if netmiko_mappings:
                try:
                    if isinstance(netmiko_mappings, str):
                        json.loads(netmiko_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        "netmiko_field_mappings必须是有效的JSON格式"
                    )

        # 验证NETCONF相关配置
        if data.get("netconf_enabled"):
            # 如果启用NETCONF，必须提供XML模板
            xml_templates = data.get("xml_templates", [])
            if not xml_templates:
                raise serializers.ValidationError("启用NETCONF时必须提供XML模板")

            # 验证XML模板数据的完整性
            for i, template in enumerate(xml_templates):
                required_fields = ["collect_method", "xml_template"]
                for field in required_fields:
                    if not template.get(field):
                        raise serializers.ValidationError(
                            f"XML模板 {i + 1} 缺少必需字段: {field}"
                        )

            # 如果提供了netconf_field_mappings，验证JSON格式
            netconf_mappings = data.get("netconf_field_mappings")
            if netconf_mappings:
                try:
                    if isinstance(netconf_mappings, str):
                        json.loads(netconf_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        "netconf_field_mappings必须是有效的JSON格式"
                    )

        if data.get("snmp_enabled"):
            snmp_oids = data.get("snmp_oids", [])
            if not snmp_oids:
                raise serializers.ValidationError("启用SNMP时必须提供至少一个OID")

        if data.get("restconf_enabled") and not data.get("restconf_endpoint"):
            raise serializers.ValidationError("启用RESTCONF时必须提供端点路径")

        if data.get("restconf_enabled"):
            restconf_method = data.get("restconf_method", "GET")
            if restconf_method != "GET":
                raise serializers.ValidationError("当前RESTCONF仅支持GET方法")

        if data.get("telemetry_enabled") and not data.get("telemetry_subscription_path"):
            raise serializers.ValidationError("启用Telemetry时必须提供订阅路径")

        return data

    def create(self, validated_data):
        from django.db import transaction
        from apps.device_api.models import DeviceCollectionPlans

        # 处理summary_plan_id
        summary_plan_id = validated_data.pop("summary_plan_id", None)
        if summary_plan_id:
            try:
                summary_plan = DeviceCollectionPlans.objects.get(id=summary_plan_id)
                validated_data["summary_plan"] = summary_plan
            except DeviceCollectionPlans.DoesNotExist:
                raise serializers.ValidationError(
                    f"汇总方案ID {summary_plan_id} 不存在"
                )
        else:
            raise serializers.ValidationError("必须提供summary_plan_id")

        xml_templates_data = validated_data.pop("xml_templates", [])

        try:
            with transaction.atomic():
                # 创建采集方案
                collection_plan = DeviceSubCollectionPlan.objects.create(
                    **validated_data
                )

                # 如果启用了NETCONF且有XML模板，创建XML模板
                if collection_plan.netconf_enabled and xml_templates_data:
                    for template_data in xml_templates_data:
                        NetconfXMLTemplate.objects.create(
                            collection_plan=collection_plan, **template_data
                        )

                return collection_plan

        except Exception as e:
            raise serializers.ValidationError(f"创建失败: {str(e)}")


class DeviceSubCollectionPlanUpdateSerializer(serializers.ModelSerializer):
    """设备采集方案更新序列化器。

    处理器相关字段为可选：未传或传 false/空 时按「未启用」处理，仅使用字段映射。
    """

    summary_plan_id = serializers.IntegerField(
        write_only=True,
        required=False,
        help_text="汇总方案ID（可选，用于更换汇总方案）",
    )
    xml_templates = serializers.ListField(
        child=serializers.DictField(), required=False, help_text="NETCONF XML模板列表"
    )

    class Meta:
        model = DeviceSubCollectionPlan
        fields = [
            "id",
            "summary_plan_id",
            "name",
            "description",
            "collection_type",
            "textfsm_template",
            "netmiko_enabled",
            "netmiko_path",
            "netmiko_method",
            "netmiko_field_mappings",
            "netmiko_processor_enabled",
            "netmiko_processor",
            "netconf_enabled",
            "netconf_path",
            "netconf_field_mappings",
            "netconf_processor_enabled",
            "netconf_processor",
            "snmp_enabled",
            "snmp_version",
            "snmp_oids",
            "snmp_path",
            "snmp_field_mappings",
            "snmp_processor_enabled",
            "snmp_processor",
            "restconf_enabled",
            "restconf_endpoint",
            "restconf_method",
            "restconf_path",
            "restconf_field_mappings",
            "restconf_processor_enabled",
            "restconf_processor",
            "telemetry_enabled",
            "telemetry_subscription_path",
            "telemetry_sampling_interval",
            "telemetry_data_format",
            "telemetry_path",
            "telemetry_field_mappings",
            "telemetry_processor_enabled",
            "telemetry_processor",
            "xml_templates",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "netmiko_processor_enabled": {"required": False},
            "netmiko_processor": {"required": False, "allow_blank": True},
            "netconf_processor_enabled": {"required": False},
            "netconf_processor": {"required": False, "allow_blank": True},
            "snmp_processor_enabled": {"required": False},
            "snmp_processor": {"required": False, "allow_blank": True},
            "restconf_processor_enabled": {"required": False},
            "restconf_processor": {"required": False, "allow_blank": True},
            "telemetry_processor_enabled": {"required": False},
            "telemetry_processor": {"required": False, "allow_blank": True},
        }

    def _instance_has_xml_templates(self) -> bool:
        if not self.instance:
            return False
        try:
            templates = getattr(self.instance, "xml_templates", None)
            if templates is None:
                return False
            if hasattr(templates, "exists"):
                return templates.exists()
            return bool(templates)
        except Exception:
            return False

    def validate(self, data):
        # 在更新时，如果字段没有传入，从实例中获取现有值
        if self.instance:
            enabled_methods = {
                "netmiko_enabled": data.get("netmiko_enabled", self.instance.netmiko_enabled),
                "netconf_enabled": data.get("netconf_enabled", self.instance.netconf_enabled),
                "snmp_enabled": data.get("snmp_enabled", self.instance.snmp_enabled),
                "restconf_enabled": data.get("restconf_enabled", self.instance.restconf_enabled),
                "telemetry_enabled": data.get("telemetry_enabled", self.instance.telemetry_enabled),
            }
        else:
            enabled_methods = {
                "netmiko_enabled": data.get("netmiko_enabled", False),
                "netconf_enabled": data.get("netconf_enabled", False),
                "snmp_enabled": data.get("snmp_enabled", False),
                "restconf_enabled": data.get("restconf_enabled", False),
                "telemetry_enabled": data.get("telemetry_enabled", False),
            }

        netmiko_enabled = enabled_methods["netmiko_enabled"]
        netconf_enabled = enabled_methods["netconf_enabled"]
        snmp_enabled = enabled_methods["snmp_enabled"]
        restconf_enabled = enabled_methods["restconf_enabled"]
        telemetry_enabled = enabled_methods["telemetry_enabled"]

        # 验证至少选择一种采集方式
        if not any(enabled_methods.values()):
            raise serializers.ValidationError(
                "至少需要启用一种采集方式（NETCONF、Netmiko、SNMP、RESTCONF 或 Telemetry）"
            )

        # 验证Netmiko相关配置
        if netmiko_enabled:
            # 如果提供了netmiko_field_mappings，验证JSON格式
            netmiko_mappings = data.get("netmiko_field_mappings")
            if netmiko_mappings:
                try:
                    if isinstance(netmiko_mappings, str):
                        json.loads(netmiko_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        "netmiko_field_mappings必须是有效的JSON格式"
                    )

        # 验证NETCONF相关配置
        if netconf_enabled:
            # 如果启用NETCONF，显式传入时必须非空；未传入时允许沿用现有模板
            xml_templates = data.get("xml_templates", None)
            if xml_templates is None:
                has_existing_templates = self._instance_has_xml_templates()
                if not has_existing_templates:
                    raise serializers.ValidationError("启用NETCONF时必须提供XML模板")
            elif not xml_templates:
                raise serializers.ValidationError("启用NETCONF时必须提供XML模板")

            # 验证XML模板数据的完整性
            for i, template in enumerate(xml_templates or []):
                if not template.get("collect_method"):
                    raise serializers.ValidationError(f"XML模板[{i}]必须包含采集方法")
                if not template.get("xml_template"):
                    raise serializers.ValidationError(f"XML模板[{i}]必须包含XML内容")

            # 如果提供了netconf_field_mappings，验证JSON格式
            netconf_mappings = data.get("netconf_field_mappings")
            if netconf_mappings:
                try:
                    if isinstance(netconf_mappings, str):
                        json.loads(netconf_mappings)
                except json.JSONDecodeError:
                    raise serializers.ValidationError(
                        "netconf_field_mappings必须是有效的JSON格式"
                    )

        if snmp_enabled:
            snmp_oids = data.get("snmp_oids", self.instance.snmp_oids if self.instance else [])
            if not snmp_oids:
                raise serializers.ValidationError("启用SNMP时必须提供至少一个OID")

        if restconf_enabled:
            restconf_endpoint = data.get(
                "restconf_endpoint",
                self.instance.restconf_endpoint if self.instance else "",
            )
            if not restconf_endpoint:
                raise serializers.ValidationError("启用RESTCONF时必须提供端点路径")
            restconf_method = data.get(
                "restconf_method",
                self.instance.restconf_method if self.instance else "GET",
            )
            if restconf_method != "GET":
                raise serializers.ValidationError("当前RESTCONF仅支持GET方法")

        if telemetry_enabled:
            telemetry_subscription_path = data.get(
                "telemetry_subscription_path",
                self.instance.telemetry_subscription_path if self.instance else "",
            )
            if not telemetry_subscription_path:
                raise serializers.ValidationError("启用Telemetry时必须提供订阅路径")

        return data

    def to_representation(self, instance):
        """重写to_representation方法，确保xml_templates字段能正确序列化"""
        # 先处理xml_templates字段，避免在super()调用时出错
        xml_templates_data = []
        try:
            if hasattr(instance, "xml_templates"):
                # 如果是RelatedManager，调用all()方法获取查询集
                if hasattr(instance.xml_templates, "all"):
                    templates = instance.xml_templates.all()
                    if templates.exists():
                        xml_templates_data = NetconfXMLTemplateSerializer(
                            templates, many=True
                        ).data
                    else:
                        xml_templates_data = []
                else:
                    # 如果已经是列表或其他类型
                    xml_templates_data = NetconfXMLTemplateSerializer(
                        instance.xml_templates, many=True
                    ).data
            else:
                xml_templates_data = []
        except Exception as e:
            # 如果出现任何错误，返回空列表
            xml_templates_data = []

        # 创建一个临时的数据字典，不包含xml_templates字段
        temp_data = {}
        for field_name in self.fields:
            if field_name != "xml_templates":
                try:
                    field = self.fields[field_name]
                    if hasattr(instance, field_name):
                        value = getattr(instance, field_name)
                        if hasattr(field, "to_representation"):
                            temp_data[field_name] = field.to_representation(value)
                        else:
                            temp_data[field_name] = value
                    else:
                        temp_data[field_name] = None
                except Exception:
                    temp_data[field_name] = None

        # 手动设置xml_templates字段
        temp_data["xml_templates"] = xml_templates_data

        return temp_data

    def update(self, instance, validated_data):
        from django.db import transaction
        from apps.device_api.models import DeviceCollectionPlans

        # 处理summary_plan_id
        summary_plan_id = validated_data.pop("summary_plan_id", None)
        if summary_plan_id:
            try:
                summary_plan = DeviceCollectionPlans.objects.get(id=summary_plan_id)
                validated_data["summary_plan"] = summary_plan
            except DeviceCollectionPlans.DoesNotExist:
                raise serializers.ValidationError(
                    f"汇总方案ID {summary_plan_id} 不存在"
                )

        xml_templates_data = validated_data.pop("xml_templates", None)

        try:
            with transaction.atomic():
                # 处理字段映射的默认值
                if (
                    "netmiko_field_mappings" in validated_data
                    and not validated_data["netmiko_field_mappings"]
                ):
                    validated_data["netmiko_field_mappings"] = {}
                if (
                    "netconf_field_mappings" in validated_data
                    and not validated_data["netconf_field_mappings"]
                ):
                    validated_data["netconf_field_mappings"] = {}

                # 更新采集方案
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.save()

                # 处理XML模板
                if (
                    xml_templates_data is not None
                ):  # 只有当明确传入xml_templates时才处理
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
                template.id: template for template in instance.xml_templates.all()
            }

            # 用于跟踪已处理的模板ID
            processed_template_ids = set()

            for template_data in new_templates_data:
                template_id = template_data.get("id")

                if template_id and template_id in existing_templates:
                    # 更新现有模板
                    existing_template = existing_templates[template_id]
                    for attr, value in template_data.items():
                        if attr != "id":  # 不更新ID字段
                            setattr(existing_template, attr, value)
                    existing_template.save()
                    processed_template_ids.add(template_id)
                else:
                    # 创建新模板
                    NetconfXMLTemplate.objects.create(
                        collection_plan=instance, **template_data
                    )

            # 删除未处理的现有模板（即多余的模板）
            templates_to_delete = [
                template_id
                for template_id in existing_templates.keys()
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

    def validate_collect_method(self, value):
        if value not in {"get", "get_config"}:
            raise serializers.ValidationError("collect_method 仅支持 get / get_config")
        return value

    class Meta:
        model = NetconfXMLTemplate
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]


class PlansToDeviceSerializer(serializers.ModelSerializer):
    """采集方案和设备关联序列化"""

    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = PlansToDevice
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]

    def create(self, validated_data):
        """
        重写 create
        """
        manage_ip = validated_data.get("manage_ip")
        plan = validated_data.get("plan")
        device_serial_num = validated_data.get("device_serial_num", "")
        profile_code = validated_data.get("profile_code", "")

        device = None
        if manage_ip:
            device = NetworkDevice.objects.filter(manage_ip=manage_ip).first()
        if device:
            if not device_serial_num:
                validated_data["device_serial_num"] = device.serial_num
                device_serial_num = device.serial_num
            if not profile_code:
                discovery_state = DeviceDiscoveryState.objects.filter(
                    device_serial_num=device.serial_num
                ).first()
                validated_data["profile_code"] = (
                    getattr(discovery_state, "profile_code", "")
                    or validated_data.get("profile_code", "")
                )
            validated_data.setdefault("last_bound_at", timezone.now())

        # 幂等创建：如果已存在则直接返回，不抛错
        qs = PlansToDevice.objects.filter(
            device_serial_num=device_serial_num,
            plan=plan,
        ).order_by("id")
        existed = qs.first()
        if existed:
            return existed

        return PlansToDevice.objects.create(**validated_data)


class DeviceFactsSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)
    vendor_alias = serializers.CharField(source="vendor.alias", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    model_name = serializers.CharField(source="model.name", read_only=True)
    legacy_plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = NetworkDevice
        fields = [
            "id",
            "serial_num",
            "manage_ip",
            "name",
            "vendor_name",
            "vendor_alias",
            "category_name",
            "model_name",
            "soft_version",
            "patch_version",
            "legacy_plan_name",
        ]


class DeviceDiscoveryStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceDiscoveryState
        fields = [
            "profile_code",
            "last_discovered_at",
            "last_discovery_status",
            "last_discovery_error",
        ]


class DeviceCapabilitiesSerializer(serializers.Serializer):
    serial_num = serializers.CharField()
    manage_ip = serializers.CharField()
    profile_code = serializers.CharField()
    supported_collection_types = serializers.ListField(child=serializers.CharField())
    preferred_methods = serializers.DictField()
    fallback_methods = serializers.DictField()
    bindings = serializers.ListField(child=serializers.DictField())


class NetconfXMLTemplateListSerializer(serializers.ModelSerializer):
    """NETCONF XML模板列表序列化器"""

    collection_plan_name = serializers.CharField(
        source="collection_plan.name", read_only=True
    )
    summary_plan_name = serializers.CharField(
        source="collection_plan.summary_plan.name", read_only=True
    )
    summary_plan_vendor = serializers.CharField(
        source="collection_plan.summary_plan.vendor", read_only=True
    )
    summary_plan_device_type = serializers.CharField(
        source="collection_plan.summary_plan.device_type", read_only=True
    )

    class Meta:
        model = NetconfXMLTemplate
        fields = [
            "id",
            "collect_method",
            "description",
            "collection_plan_name",
            "summary_plan_name",
            "summary_plan_vendor",
            "summary_plan_device_type",
            "created_at",
            "updated_at",
        ]


class CollectionFilterSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(help_text="采集方案ID", required=False)
    plan_name = serializers.CharField(help_text="采集方案名称", required=False)
    device_ip = serializers.CharField(help_text="设备IP地址", required=False)
    device_name = serializers.CharField(
        help_text="设备名称", required=False, allow_blank=True
    )
    device_type = serializers.CharField(help_text="设备类型", required=False)
    vendor = serializers.CharField(help_text="厂商", required=False, allow_blank=True)
    collection_method = serializers.CharField(help_text="采集方式", required=False)
    method_name = serializers.CharField(
        help_text="采集方法名称", required=False, allow_blank=True
    )
    status = serializers.CharField(help_text="采集状态", required=False)
    start_date = serializers.CharField(help_text="开始采集时间", required=False)
    end_date = serializers.CharField(help_text="结束采集日期", required=False)
    start_time = serializers.CharField(help_text="开始采集时间", required=False)
    end_time = serializers.CharField(help_text="结束采集时间", required=False)
    days = serializers.IntegerField(help_text="最近天数", required=False)
    page = serializers.IntegerField(help_text="页码", required=False, default=1)
    page_size = serializers.IntegerField(
        help_text="每页大小", required=False, default=10
    )
    sort_by = serializers.CharField(
        help_text="排序字段", required=False, default="collected_at"
    )
    sort_order = serializers.CharField(
        help_text="排序方向", required=False, default="desc"
    )


class CollectionResultListSerializer(serializers.Serializer):
    """采集结果列表序列化器"""

    _id = serializers.CharField(read_only=True, help_text="MongoDB文档ID")
    plan_id = serializers.IntegerField(help_text="采集方案ID")
    plan_name = serializers.CharField(help_text="采集方案名称")
    device_ip = serializers.CharField(help_text="设备IP地址")
    device_name = serializers.CharField(help_text="设备名称")
    idc_name = serializers.CharField(help_text="机房名称")
    device_type = serializers.CharField(help_text="设备类型")
    vendor = serializers.CharField(help_text="厂商")
    collection_method = serializers.CharField(help_text="采集方式")
    method_name = serializers.CharField(help_text="采集方法名称")
    collected_at = serializers.SerializerMethodField(help_text="采集时间")
    status = serializers.CharField(help_text="采集状态")

    @staticmethod
    def get_collected_at(obj):
        """格式化采集时间为标准格式"""

        collected_at = obj.get("collected_at")
        if not collected_at:
            return None

        try:
            # 如果是字符串格式，先解析为datetime对象
            if isinstance(collected_at, str):
                # 处理ISO 8601格式
                if "T" in collected_at and "+" in collected_at:
                    # 移除时区信息，只保留本地时间
                    dt = datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
                    # 转换为本地时间（这里假设是北京时间）
                    local_tz = pytz.timezone("Asia/Shanghai")
                    dt = dt.astimezone(local_tz)
                else:
                    dt = datetime.fromisoformat(collected_at)
            else:
                # 如果已经是datetime对象
                dt = collected_at

            # 格式化为标准格式：YYYY-MM-DD HH:MM:SS
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            # 如果解析失败，返回原始值
            return str(collected_at)


class CollectionResultDetailSerializer(CollectionResultListSerializer):
    """采集结果详情序列化器"""

    data = serializers.JSONField(help_text="原始数据")
    task_errors = serializers.ListField(
        child=serializers.CharField(), help_text="执行错误信息"
    )
    processed_data = serializers.JSONField(help_text="中间层数据")
    processed_status = serializers.CharField(help_text="处理状态")
    processed_error = serializers.CharField(help_text="处理报错信息")


class CollectionResultByPlanSerializer(CollectionResultListSerializer):
    """采集结果不展示报错信息序列化器"""

    data = serializers.JSONField(help_text="原始数据")
    processed_data = serializers.JSONField(help_text="函数处理后的数据")
