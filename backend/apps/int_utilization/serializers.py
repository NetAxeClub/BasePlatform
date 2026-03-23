from apps.network_analysis.serializers import InterfaceUtilizationLegacySerializer


class InterfaceUsedNewSerializer(InterfaceUtilizationLegacySerializer):
    """旧 int_utilization 入口沿用 network_analysis 的兼容字段输出。"""
