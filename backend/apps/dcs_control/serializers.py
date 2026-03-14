from rest_framework import serializers

from apps.dcs_control.models import FirewallPolicyAuditRecord


class FirewallPolicyAuditRecordSerializer(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = FirewallPolicyAuditRecord
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
