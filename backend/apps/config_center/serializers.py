# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      serializers
   Description:
   Author:          Lijiamin
   date：           2022/10/1 13:16
-------------------------------------------------
   Change Activity:
                    2022/10/1 13:16
-------------------------------------------------
"""
from rest_framework import serializers

from apps.config_center.config_parse.structured.policy import preview_merged_drift_policy
from utils.custom.exception import SerializerValidateError
from .models import (
    ConfigCompliance, ConfigTemplate, TTPTemplate, ConfigBackup, ConfigComplianceResult, ConfigComplianceRule,
    BackupPolicy, StructuredDriftPolicy, StructuredDriftPolicyAudit
)


# 配置备份表
class ConfigBackupSerializer(serializers.ModelSerializer):
    last_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        return queryset

    class Meta:
        model = ConfigBackup
        fields = '__all__'


class ChildrenField(serializers.StringRelatedField):

    def to_internal_value(self, value):
        return value

    def to_representation(self, value):
        """
        Serialize tagged objects to a simple textual representation.
        """
        return dict(id=value.id, name=value.name)


class ConfigComplianceRuleSerializer(serializers.ModelSerializer):
    children = ChildrenField(many=True, read_only=True)

    class Meta:
        model = ConfigComplianceRule
        fields = ('id', 'name', 'children', 'parent')


# 配置合规表
class ConfigComplianceSerializer(serializers.ModelSerializer):
    datetime = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        # select_related for "to-one" relationships
        # prefetch_related for "to-many" relationships
        # queryset = queryset.select_related('config_set')
        # queryset = queryset.prefetch_related(
        #     'part')
        #
        # # Prefetch for subsets of relationships
        # queryset = queryset.prefetch_related(
        #     Prefetch('unaffiliated_attendees',
        #              queryset=NetworkDevice.objects.filter(organization__isnull=True))
        # )
        return queryset

    class Meta:
        model = ConfigCompliance
        fields = '__all__'


# 配置合规结果表
class ConfigComplianceResultSerializer(serializers.ModelSerializer):
    log_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    backup_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True, allow_null=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        return queryset

    class Meta:
        model = ConfigComplianceResult
        fields = '__all__'


# 配置模板表
class ConfigTemplateSerializer(serializers.ModelSerializer):
    """配置模板表"""
    datetime = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = ConfigTemplate
        fields = '__all__'


# TTP模板表
class TTPTemplateSerializer(serializers.ModelSerializer):
    """TTP模板表"""
    datetime = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = TTPTemplate
        fields = '__all__'


# 配置策略
class ConfigBackupPolicySerializer(serializers.ModelSerializer):

    class Meta:
        model = BackupPolicy
        fields = '__all__'

    def validate_vendor(self, value):
        """
        校验 vendor 是否已存在
        """
        # 如果是更新操作，排除当前实例
        if self.instance:
            if BackupPolicy.objects.filter(vendor=value).exclude(pk=self.instance.pk).exists():
                raise SerializerValidateError(f"Vendor '{value}' 已经存在！")
        else:
            if BackupPolicy.objects.filter(vendor=value).exists():
                raise SerializerValidateError(f"Vendor '{value}' 已经存在！")
        return value


class StructuredDriftPolicySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = StructuredDriftPolicy
        fields = '__all__'

    def validate_policy_content(self, value):
        preview = preview_merged_drift_policy(value or {})
        validation = preview.get('validation') or {}
        if not validation.get('is_valid'):
            raise SerializerValidateError('漂移策略不合法: {}'.format('; '.join(validation.get('errors') or [])))
        return value or {}


class StructuredDriftPolicyAuditSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    policy_name = serializers.CharField(source='policy.name', read_only=True)
    policy_version = serializers.CharField(source='policy.version', read_only=True)
    previous_policy_name = serializers.CharField(source='previous_policy.name', read_only=True)
    previous_policy_version = serializers.CharField(source='previous_policy.version', read_only=True)

    class Meta:
        model = StructuredDriftPolicyAudit
        fields = '__all__'
