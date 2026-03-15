import json

from rest_framework import serializers

from apps.workflow_center.inspection import (
    inspection_payload,
    inspection_scope,
    inspection_summary,
    inspection_type,
)
from apps.workflow_center.models import (
    WorkflowExecution,
    WorkflowHostVar,
    WorkflowInventory,
)


class WorkflowExecutionSerializer(serializers.ModelSerializer):
    commit_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    inspection_scope = serializers.SerializerMethodField()
    inspection_type = serializers.SerializerMethodField()
    inspection_summary = serializers.SerializerMethodField()
    inspection_payload = serializers.SerializerMethodField()

    class Meta:
        model = WorkflowExecution
        fields = (
            "id",
            "task_id",
            "origin",
            "task_result",
            "order_code",
            "device",
            "device_id",
            "commit_user",
            "commit_time",
            "task",
            "method",
            "class_method",
            "remote_ip",
            "event",
            "kwargs",
            "ttp",
            "commands",
            "back_off_commands",
            "state",
            "code",
            "inspection_scope",
            "inspection_type",
            "inspection_summary",
            "inspection_payload",
        )

    def get_inspection_scope(self, obj):
        if getattr(obj, "task", "") != "巡检":
            return ""
        return inspection_scope(obj)

    def get_inspection_type(self, obj):
        if getattr(obj, "task", "") != "巡检":
            return ""
        return inspection_type(obj)

    def get_inspection_summary(self, obj):
        if getattr(obj, "task", "") != "巡检":
            return {}
        return inspection_summary(obj)

    def get_inspection_payload(self, obj):
        if getattr(obj, "task", "") != "巡检":
            return {}
        return inspection_payload(obj)


class WorkflowInventoryField(serializers.StringRelatedField):
    def to_internal_value(self, value):
        if isinstance(value, dict):
            return value
        raise serializers.ValidationError("inventory 数据格式不正确")

    def to_representation(self, value):
        return {"id": value.id, "name": value.name}


class WorkflowHostVarSerializer(serializers.ModelSerializer):
    inventories = WorkflowInventoryField(many=True, read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.prefetch_related("inventories")

    class Meta:
        model = WorkflowHostVar
        fields = "__all__"


class WorkflowHostField(serializers.StringRelatedField):
    def to_internal_value(self, value):
        if isinstance(value, dict):
            return value
        raise serializers.ValidationError("hosts 格式不正确")

    def to_representation(self, value):
        return {
            "id": value.id,
            "host": value.host,
            "task": value.task,
            "object_name": value.object_name,
        }


class WorkflowInventorySerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(read_only=True, format="%Y-%m-%d %H:%M:%S")
    hosts = WorkflowHostField(many=True)
    host_details = serializers.SerializerMethodField(read_only=True)

    @staticmethod
    def setup_eager_loading(queryset):
        return queryset.prefetch_related("hosts")

    class Meta:
        model = WorkflowInventory
        fields = "__all__"

    def get_host_details(self, obj):
        host_vars = WorkflowHostVar.objects.prefetch_related("inventories").filter(inventories=obj.id)
        return WorkflowHostVarSerializer(host_vars, many=True).data

    def create(self, validated_data):
        hosts = validated_data.get("hosts")
        validated_data.pop("hosts")
        instance = WorkflowInventory.objects.create(**validated_data)
        if hosts and isinstance(hosts, list):
            current = WorkflowInventory.objects.get(id=instance.id)
            for host in hosts:
                current.hosts.add(WorkflowHostVar.objects.get(id=host["id"]))
        return instance

    def update(self, instance, validated_data):
        instance.name = validated_data.get("name", instance.name)
        instance.variables = validated_data.get("variables", instance.variables)
        instance.description = validated_data.get("description", instance.description)
        instance.task = validated_data.get("task", instance.task)
        instance.save()
        hosts = validated_data.get("hosts", instance.hosts)
        if isinstance(hosts, list):
            current = WorkflowInventory.objects.get(id=instance.id)
            current.hosts.clear()
            for host in hosts:
                current.hosts.add(WorkflowHostVar.objects.get(id=host["id"]))
        return instance
