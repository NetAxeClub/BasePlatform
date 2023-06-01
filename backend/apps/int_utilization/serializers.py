from rest_framework import serializers

from .models import InterfaceUsed


class InterfaceUsedNewSerializer(serializers.ModelSerializer):
    """接口利用率序列化"""
    log_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S', read_only=True)

    class Meta:
        model = InterfaceUsed
        fields = '__all__'
