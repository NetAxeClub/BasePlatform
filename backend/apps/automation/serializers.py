# 自动化设备数据采集方案清单
from rest_framework import serializers
# import xml.etree.ElementTree as ET
import json
from apps.automation.models import (CollectionPlan, CollectionRule, CollectionMatchRule,
                                    AutoFlow, AutomationInventory, AutoVars)


# 采集方案序列化
class CollectionPlanSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        # queryset = queryset.prefetch_related('relate_device')

        return queryset

    class Meta:
        model = CollectionPlan
        fields = '__all__'


# 采集规则匹配规则序列化
class CollectionMatchRuleSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source='get_operator_display', read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        # queryset = queryset.prefetch_related('match_rule')
        queryset = queryset.select_related('rule')
        return queryset

    class Meta:
        model = CollectionMatchRule
        fields = '__all__'


# 采集规则序列化
class CollectionRuleSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(source='vendor.name', read_only=True)
    match_rule = CollectionMatchRuleSerializer(many=True, read_only=True)

    # @staticmethod
    # def is_valid_xml(xml_string):
    #     try:
    #         ET.fromstring(xml_string)
    #         return True
    #     except ET.ParseError:
    #         return False
    #
    # def validate(self, data):
    #     # 自定义校验逻辑
    #     if data['method'] == 'CLI':
    #         if not isinstance(data['execute'], str):
    #             raise serializers.ValidationError("命令校验失败，CLI校验内容不是标准命令行.")
    #     elif data['method'] == 'NETCONF':
    #         if not CollectionRule.is_valid_xml(data['execute']):
    #             raise serializers.ValidationError("命令校验失败，NETCONF校验内容不符合XML规范.")
    #     elif data['method'] == 'REST_API':
    #         if not isinstance(json.loads(data['execute']), dict):
    #             raise serializers.ValidationError("命令校验失败，REST_API校验内容不是dict类型.")
    #     return data
    #
    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        # queryset = queryset.prefetch_related('match_rule')
        queryset = queryset.prefetch_related('match_rule')
        return queryset

    class Meta:
        model = CollectionRule
        fields = '__all__'


# 自动化工作流
class AutoFlowSerializer(serializers.ModelSerializer):
    commit_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = AutoFlow
        fields = '__all__'


# 自动化设备清单表
class AutoVarsSerializer(serializers.ModelSerializer):
    to_inventory = serializers.StringRelatedField(many=True, read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.prefetch_related(
            'to_inventory')
        return queryset

    class Meta:
        model = AutoVars
        fields = '__all__'


class AnsGroupHostsField(serializers.StringRelatedField):

    def to_internal_value(self, value):
        # value = json.loads(value)
        if isinstance(value, dict):
            return value
        else:
            raise serializers.ValidationError("ans_group_hosts with name: %s 格式不正确" % value)

    def to_representation(self, value):
        """
        Serialize tagged objects to a simple textual representation.
        """
        return dict(id=value.id, ans_host=value.ans_host, task=value.task, ans_obj=value.ans_obj)


# 自动化设备清单表
class AutomationInventorySerializer(serializers.ModelSerializer):
    ans_group_datetime = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')
    # ans_group_hosts = AutoVarsSerializer(many=True)
    ans_group_hosts = AnsGroupHostsField(many=True)
    # ans_group_hosts = serializers.ManyRelatedField(many=True, child_relation='ans_group_hosts')
    # 自定义外键显示的方法，后面写get_ans_host来与之对应实现嵌套
    ans_host = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.prefetch_related(
            'ans_group_hosts')
        return queryset

    class Meta:
        model = AutomationInventory
        fields = '__all__'

    def get_ans_host(self, obj):
        _vars = AutoVars.objects.prefetch_related(
            'to_inventory').filter(to_inventory=obj.id)
        return AutoVarsSerializer(_vars, many=True).data

    def create(self, validated_data):
        """
        重写 create
        """
        ans_group_hosts = validated_data.get('ans_group_hosts')
        validated_data.pop('ans_group_hosts')
        instance = AutomationInventory.objects.create(**validated_data)
        if ans_group_hosts:
            print('ans_group_hosts', ans_group_hosts, type(ans_group_hosts))
            if isinstance(ans_group_hosts, list) and instance:
                dev_obj = AutomationInventory.objects.get(id=instance.id)
                if ans_group_hosts:
                    for _ans_group_hosts in ans_group_hosts:
                        dev_obj.ans_group_hosts.add(AutoVars.objects.get(id=_ans_group_hosts['id']))
                else:
                    dev_obj.ans_group_hosts.clear()
        return instance

    def update(self, instance, validated_data):
        """
        重写 update
        """
        instance.ans_group_name = validated_data.get('ans_group_name', instance.ans_group_name)
        instance.ans_group_vars = validated_data.get('ans_group_vars', instance.ans_group_vars)
        instance.ans_group_memo = validated_data.get('ans_group_memo', instance.ans_group_memo)
        instance.task = validated_data.get('task', instance.task)
        instance.save()
        ans_group_hosts = validated_data.get('ans_group_hosts', instance.ans_group_hosts)
        if ans_group_hosts:
            if isinstance(ans_group_hosts, list):
                dev_obj = AutomationInventory.objects.get(id=instance.id)
                dev_obj.ans_group_hosts.clear()
                if ans_group_hosts:
                    for _ans_group_hosts in ans_group_hosts:
                        dev_obj.ans_group_hosts.add(AutoVars.objects.get(id=_ans_group_hosts['id']))
                else:
                    dev_obj.ans_group_hosts.clear()
        return instance