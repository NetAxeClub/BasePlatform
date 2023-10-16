# 自动化设备数据采集方案清单
from rest_framework import serializers
# import xml.etree.ElementTree as ET
# import json
from apps.automation.models import CollectionPlan, CollectionRule, CollectionMatchRule


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