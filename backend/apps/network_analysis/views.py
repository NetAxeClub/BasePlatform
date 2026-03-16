from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.decorators import action

from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.network_analysis.models import (
    AddressTraceSnapshot,
    AnalysisRun,
    InterfaceUtilizationSnapshot,
)
from apps.network_analysis.serializers import (
    AddressTraceSnapshotSerializer,
    AnalysisRunSerializer,
    InterfaceUtilizationSnapshotSerializer,
)
from apps.network_analysis.services import (
    AddressTrackingAnalysisService,
    InterfaceUtilizationAnalysisService,
    NetworkAnalysisOrchestratorService,
)


class InterfaceUtilizationSnapshotViewSet(CustomViewBase):
    queryset = InterfaceUtilizationSnapshot.objects.all().order_by("-snapshot_time")
    serializer_class = InterfaceUtilizationSnapshotSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ("manage_ip", "device_serial_num", "component_scope", "dominant_speed")
    search_fields = ("manage_ip", "device_name", "component_name")
    ordering_fields = ("snapshot_time", "utilization_percent", "manage_ip")
    pagination_class = LargeResultsSetPagination

    @action(detail=False, methods=["post"])
    def rebuild(self, request):
        result = InterfaceUtilizationAnalysisService.refresh(
            device_ip=request.data.get("manage_ip"),
            execute_time=request.data.get("execute_time"),
        )
        return JsonResponse({"code": 200, "message": "重建完成", "data": result})

    @action(detail=False, methods=["get"])
    def overview(self, request):
        result = InterfaceUtilizationAnalysisService.overview(
            device_ip=request.GET.get("manage_ip"),
            execute_time=request.GET.get("execute_time"),
        )
        return JsonResponse({"code": 200, "message": "获取成功", "data": result})

    @action(detail=False, methods=["get"])
    def quality(self, request):
        result = InterfaceUtilizationAnalysisService.quality_summary(
            device_ip=request.GET.get("manage_ip"),
            execute_time=request.GET.get("execute_time"),
        )
        return JsonResponse({"code": 200, "message": "获取成功", "data": result})


class AddressTraceSnapshotViewSet(CustomViewBase):
    queryset = AddressTraceSnapshot.objects.all().order_by("-observed_at")
    serializer_class = AddressTraceSnapshotSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ("ip_address", "manage_ip", "trace_status", "trace_method")
    search_fields = ("ip_address", "mac_address", "manage_ip", "device_name", "interface_name")
    ordering_fields = ("observed_at", "ip_address", "manage_ip")
    pagination_class = LargeResultsSetPagination

    @action(detail=False, methods=["post"])
    def rebuild(self, request):
        result = AddressTrackingAnalysisService.refresh(
            ip_address=request.data.get("ip_address")
        )
        return JsonResponse({"code": 200, "message": "重建完成", "data": result})

    @action(detail=False, methods=["get"])
    def overview(self, request):
        result = AddressTrackingAnalysisService.overview(
            ip_address=request.GET.get("ip_address"),
            execute_time=request.GET.get("execute_time"),
        )
        return JsonResponse({"code": 200, "message": "获取成功", "data": result})

    @action(detail=False, methods=["get"])
    def quality(self, request):
        result = AddressTrackingAnalysisService.quality_summary(
            ip_address=request.GET.get("ip_address"),
            execute_time=request.GET.get("execute_time"),
        )
        return JsonResponse({"code": 200, "message": "获取成功", "data": result})


class AnalysisRunViewSet(CustomViewBase):
    queryset = AnalysisRun.objects.all().order_by("-created_at")
    serializer_class = AnalysisRunSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ("run_kind", "status", "target_manage_ip", "target_ip_address")
    search_fields = ("triggered_by", "error_message")
    ordering_fields = ("created_at", "updated_at", "started_at", "finished_at")
    pagination_class = LargeResultsSetPagination

    @action(detail=False, methods=["post"])
    def rebuild_all(self, request):
        result = NetworkAnalysisOrchestratorService.refresh_all(
            manage_ip=request.data.get("manage_ip"),
            ip_address=request.data.get("ip_address"),
            triggered_by=request.data.get("triggered_by", "api"),
        )
        return JsonResponse({"code": 200, "message": "统一重建完成", "data": result})
