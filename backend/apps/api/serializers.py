# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      serializers
   Description:
   Author:          Lijiamin
   date：           2022/7/29 10:51
-------------------------------------------------
   Change Activity:
                    2022/7/29 10:51
-------------------------------------------------
"""
from rest_framework import serializers
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django_celery_results.models import TaskResult
from apps.asset.models import (NetZone, IdcModel, Rack,  AssetIpInfo,)


class IntervalScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntervalSchedule
        fields = '__all__'


class PeriodicTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = PeriodicTask
        fields = '__all__'


# celery 任务结果表
class TaskResultSerializer(serializers.ModelSerializer):
    date_done = serializers.DateTimeField(read_only=True, format='%Y-%m-%d %H:%M:%S')

    class Meta:
        model = TaskResult
        fields = '__all__'


# 网络区域
class NetZoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetZone
        fields = '__all__'


# 机房机柜
class CmdbRackSerializer(serializers.ModelSerializer):
    idc_model_name = serializers.CharField(source='idc_model.name', read_only=True)
    idc_name = serializers.CharField(source='idc_model.idc.name', read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.select_related('idc_model', 'idc_model__idc')
        return queryset

    class Meta:
        model = Rack
        fields = '__all__'


# 机房模块
class IdcModelSerializer(serializers.ModelSerializer):

    @staticmethod
    def setup_eager_loading(queryset):
        """ Perform necessary eager loading of data. """
        # select_related for "to-one" relationships
        # queryset = queryset.select_related('host')
        queryset = queryset.select_related('idc')
        return queryset

    class Meta:
        model = IdcModel
        fields = '__all__'


# 网络设备绑定IP信息
class AssetIpInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetIpInfo
        fields = '__all__'



