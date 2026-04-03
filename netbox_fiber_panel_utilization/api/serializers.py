from rest_framework import serializers


class ModuleUtilizationSerializer(serializers.Serializer):
    name = serializers.CharField()
    model = serializers.CharField()
    used = serializers.IntegerField()
    total = serializers.IntegerField()


class PanelUtilizationSerializer(serializers.Serializer):
    device_id = serializers.IntegerField()
    device_name = serializers.CharField()
    site = serializers.CharField(allow_null=True)
    location = serializers.CharField(allow_null=True)
    rack = serializers.CharField(allow_null=True)
    total_ports = serializers.IntegerField()
    used_ports = serializers.IntegerField()
    free_ports = serializers.IntegerField()
    utilization_percent = serializers.FloatField()
    modules = ModuleUtilizationSerializer(many=True)
