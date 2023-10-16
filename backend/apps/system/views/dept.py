# -*- coding: utf-8 -*-

"""
@author: H0nGzA1
@contact: QQ:2505811377
@Remark: 部门管理
"""
from rest_framework import serializers
from django_filters.rest_framework import DjangoFilterBackend

from apps.system.models import Dept
from utils.custom.json_response import DetailResponse, SuccessResponse
from utils.custom.serializers import CustomModelSerializer
from utils.custom.viewset import CustomModelViewSet


class DeptSerializer(CustomModelSerializer):
    """
    部门-序列化器
    """
    children = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()

    def get_children(self, data):
        queryset = Dept.objects.filter(parent_id=data.id).all()
        children = DeptSerializer(queryset, many=True).data
        if children:
            return children
        else:
            return None

    def get_status_label(self, instance):
        status = instance.status
        if status:
            return "启用"
        return "禁用"

    class Meta:
        model = Dept
        fields = '__all__'
        read_only_fields = ["id"]


class DeptCreateUpdateSerializer(CustomModelSerializer):
    """
    部门管理 创建/更新时的列化器
    """

    def create(self, validated_data):
        instance = super().create(validated_data)
        instance.dept_belong_id = instance.id
        instance.save()
        return instance

    class Meta:
        model = Dept
        fields = '__all__'


class DeptViewSet(CustomModelViewSet):
    """
    部门管理接口
    list:查询
    create:新增
    update:修改
    retrieve:单例
    destroy:删除
    """
    queryset = Dept.objects.all()
    serializer_class = DeptSerializer
    create_serializer_class = DeptCreateUpdateSerializer
    update_serializer_class = DeptCreateUpdateSerializer
    search_fields = []
    filterset_fields = {
        "parent": ["isnull"],
        "name": ["icontains"],
    }

    def list(self, request, *args, **kwargs):
        # 如果懒加载，则只返回父级
        queryset = self.filter_queryset(self.get_queryset())
        lazy = self.request.query_params.get('lazy')
        parent = self.request.query_params.get('parent')
        if lazy:
            # 如果懒加载模式，返回全部
            if not parent:
                if self.request.user.is_superuser:
                    queryset = queryset.filter(parent__isnull=True)
                else:
                    queryset = queryset.filter(id=self.request.user.dept_id)
            serializer = self.get_serializer(queryset, many=True, request=request)
            return SuccessResponse(data=serializer.data, msg="获取成功")

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, request=request)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, request=request)
        return SuccessResponse(data=serializer.data, msg="获取成功")

    def dept_lazy_tree(self, request, *args, **kwargs):
        parent = self.request.query_params.get('parent')
        queryset = self.filter_queryset(self.get_queryset())
        if not parent:
            if self.request.user.is_superuser:
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(id=self.request.user.dept_id)
        data = queryset.filter(status=True).order_by('sort').values('name', 'id', 'parent')
        return DetailResponse(data=data, msg="获取成功")