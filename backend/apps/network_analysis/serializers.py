from rest_framework import serializers

from apps.network_analysis.models import (
    AddressTraceSnapshot,
    AnalysisRun,
    InterfaceUtilizationSnapshot,
)


class InterfaceUtilizationSnapshotSerializer(serializers.ModelSerializer):
    snapshot_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = InterfaceUtilizationSnapshot
        fields = "__all__"


class AddressTraceSnapshotSerializer(serializers.ModelSerializer):
    observed_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = AddressTraceSnapshot
        fields = "__all__"


class AnalysisRunSerializer(serializers.ModelSerializer):
    started_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    finished_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = AnalysisRun
        fields = "__all__"
