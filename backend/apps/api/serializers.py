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

