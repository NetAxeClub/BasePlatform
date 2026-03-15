from rest_framework import serializers

from apps.network_analysis.models import InterfaceUtilizationSnapshot


class InterfaceUsedNewSerializer(serializers.ModelSerializer):
    """旧接口利用率接口的兼容序列化输出。"""

    host = serializers.CharField(source="device_name", read_only=True)
    host_id = serializers.CharField(source="device_serial_num", read_only=True)
    host_ip = serializers.CharField(source="manage_ip", read_only=True)
    host_type = serializers.CharField(source="dominant_speed", read_only=True)
    int_total = serializers.IntegerField(source="total_ports", read_only=True)
    int_used = serializers.IntegerField(source="used_ports", read_only=True)
    int_unused = serializers.IntegerField(source="unused_ports", read_only=True)
    utilization = serializers.FloatField(source="utilization_percent", read_only=True)
    log_time = serializers.DateTimeField(source="snapshot_time", format="%Y-%m-%d %H:%M:%S", read_only=True)

    int_used_1g = serializers.SerializerMethodField()
    int_used_10m = serializers.SerializerMethodField()
    int_used_100m = serializers.SerializerMethodField()
    int_used_10g = serializers.SerializerMethodField()
    int_used_20g = serializers.SerializerMethodField()
    int_used_25g = serializers.SerializerMethodField()
    int_used_40g = serializers.SerializerMethodField()
    int_used_100g = serializers.SerializerMethodField()
    int_used_200g = serializers.SerializerMethodField()
    int_used_400g = serializers.SerializerMethodField()
    int_used_irf = serializers.SerializerMethodField()
    int_used_auto = serializers.SerializerMethodField()
    int_unused_1g = serializers.SerializerMethodField()
    int_unused_10m = serializers.SerializerMethodField()
    int_unused_100m = serializers.SerializerMethodField()
    int_unused_10g = serializers.SerializerMethodField()
    int_unused_20g = serializers.SerializerMethodField()
    int_unused_25g = serializers.SerializerMethodField()
    int_unused_40g = serializers.SerializerMethodField()
    int_unused_100g = serializers.SerializerMethodField()
    int_unused_200g = serializers.SerializerMethodField()
    int_unused_400g = serializers.SerializerMethodField()
    int_unused_irf = serializers.SerializerMethodField()
    int_unused_auto = serializers.SerializerMethodField()

    class Meta:
        model = InterfaceUtilizationSnapshot
        fields = (
            "id",
            "host",
            "host_id",
            "host_ip",
            "host_type",
            "int_total",
            "int_used",
            "int_unused",
            "utilization",
            "int_used_1g",
            "int_used_10m",
            "int_used_100m",
            "int_used_10g",
            "int_used_20g",
            "int_used_25g",
            "int_used_40g",
            "int_used_100g",
            "int_used_200g",
            "int_used_400g",
            "int_used_irf",
            "int_used_auto",
            "int_unused_1g",
            "int_unused_10m",
            "int_unused_100m",
            "int_unused_10g",
            "int_unused_20g",
            "int_unused_25g",
            "int_unused_40g",
            "int_unused_100g",
            "int_unused_200g",
            "int_unused_400g",
            "int_unused_irf",
            "int_unused_auto",
            "log_time",
            "component_scope",
            "component_key",
            "component_name",
            "source_execute_time",
        )

    @staticmethod
    def _speed_key_map():
        return {
            "int_used_1g": "1G",
            "int_used_10m": "10M",
            "int_used_100m": "100M",
            "int_used_10g": "10G",
            "int_used_20g": "20G",
            "int_used_25g": "25G",
            "int_used_40g": "40G",
            "int_used_100g": "100G",
            "int_used_200g": "200G",
            "int_used_400g": "400G",
            "int_unused_1g": "1G",
            "int_unused_10m": "10M",
            "int_unused_100m": "100M",
            "int_unused_10g": "10G",
            "int_unused_20g": "20G",
            "int_unused_25g": "25G",
            "int_unused_40g": "40G",
            "int_unused_100g": "100G",
            "int_unused_200g": "200G",
            "int_unused_400g": "400G",
        }

    def _get_speed_count(self, obj, field_name):
        speed_name = self._speed_key_map().get(field_name, "")
        if field_name.startswith("int_used_"):
            return obj.used_speed_counts.get(speed_name, 0)
        if field_name.startswith("int_unused_"):
            return obj.unused_speed_counts.get(speed_name, 0)
        return 0

    def get_int_used_1g(self, obj):
        return self._get_speed_count(obj, "int_used_1g")

    def get_int_used_10m(self, obj):
        return self._get_speed_count(obj, "int_used_10m")

    def get_int_used_100m(self, obj):
        return self._get_speed_count(obj, "int_used_100m")

    def get_int_used_10g(self, obj):
        return self._get_speed_count(obj, "int_used_10g")

    def get_int_used_20g(self, obj):
        return self._get_speed_count(obj, "int_used_20g")

    def get_int_used_25g(self, obj):
        return self._get_speed_count(obj, "int_used_25g")

    def get_int_used_40g(self, obj):
        return self._get_speed_count(obj, "int_used_40g")

    def get_int_used_100g(self, obj):
        return self._get_speed_count(obj, "int_used_100g")

    def get_int_used_200g(self, obj):
        return self._get_speed_count(obj, "int_used_200g")

    def get_int_used_400g(self, obj):
        return self._get_speed_count(obj, "int_used_400g")

    def get_int_used_irf(self, obj):
        return 0

    def get_int_used_auto(self, obj):
        return 0

    def get_int_unused_1g(self, obj):
        return self._get_speed_count(obj, "int_unused_1g")

    def get_int_unused_10m(self, obj):
        return self._get_speed_count(obj, "int_unused_10m")

    def get_int_unused_100m(self, obj):
        return self._get_speed_count(obj, "int_unused_100m")

    def get_int_unused_10g(self, obj):
        return self._get_speed_count(obj, "int_unused_10g")

    def get_int_unused_20g(self, obj):
        return self._get_speed_count(obj, "int_unused_20g")

    def get_int_unused_25g(self, obj):
        return self._get_speed_count(obj, "int_unused_25g")

    def get_int_unused_40g(self, obj):
        return self._get_speed_count(obj, "int_unused_40g")

    def get_int_unused_100g(self, obj):
        return self._get_speed_count(obj, "int_unused_100g")

    def get_int_unused_200g(self, obj):
        return self._get_speed_count(obj, "int_unused_200g")

    def get_int_unused_400g(self, obj):
        return self._get_speed_count(obj, "int_unused_400g")

    def get_int_unused_irf(self, obj):
        return 0

    def get_int_unused_auto(self, obj):
        return 0
