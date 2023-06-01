# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      serializers
   Description:
   Author:          Lijiamin
   date：           2023/2/27 20:25
-------------------------------------------------
   Change Activity:
                    2023/2/27 20:25
-------------------------------------------------
"""
import json
from rest_framework import serializers
from .models import Organization


class BgBuSerializer(serializers.ModelSerializer):
    """组织表"""

    class Meta:
        model = Organization
        fields = ('id', 'name',)

