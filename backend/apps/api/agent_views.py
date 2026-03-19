import json
from typing import Dict, List, Optional
from uuid import uuid4

from django.http import JsonResponse
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.asset.models import NetworkDevice
from apps.dcs_control.constants import Vendor
from apps.dcs_control.models import FirewallPolicyAuditRecord
from apps.dcs_control.policy_audit import (
    build_sec_policy_audit_payload,
    extract_sec_policy_audit_summary,
    extract_sec_policy_findings,
    get_vendor_aliases,
)
from apps.dcs_control.views import sec_policy_mongo
from apps.device_api.models import DeviceDiscoveryState
from apps.device_api.platform_profiles import PlatformProfileService
from apps.network_analysis.models import (
    AddressTraceSnapshot,
    AnalysisRun,
    InterfaceUtilizationSnapshot,
)
from apps.workflow_center.inspection import inspection_payload, inspection_summary
from apps.workflow_center.models import Method, State, Tasks, WorkflowExecution


class AgentRequestAuthentication(BaseAuthentication):
    """Accept IAM middleware identities or an already authenticated Django user."""

    def authenticate(self, request):
        django_request = getattr(request, "_request", request)
        iam_user = getattr(django_request, "iam", None)
        if iam_user is not None and getattr(iam_user, "is_authenticated", False):
            return iam_user, None

        user = getattr(django_request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            return user, None
        return None


def _parse_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _response(
    *,
    task_id: Optional[str],
    execution_id: Optional[str],
    status: str,
    severity: str,
    summary: Dict,
    artifacts: Optional[List[Dict]] = None,
    audit_ref: Optional[str] = None,
    rollback_ref: Optional[str] = None,
    payload: Optional[Dict] = None,
    http_status: int = 200,
):
    body = {
        "task_id": task_id,
        "execution_id": execution_id,
        "status": status,
        "severity": severity,
        "summary": summary or {},
        "artifacts": artifacts or [],
        "audit_ref": audit_ref,
        "rollback_ref": rollback_ref,
    }
    if payload is not None:
        body["payload"] = payload
    return JsonResponse(body, status=http_status)


def _now_task_id(prefix: str) -> str:
    return f"{prefix}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"


def _workflow_status(state: str) -> str:
    if state in (State.SUCCEEDED, State.FINISH):
        return "SUCCEEDED"
    if state == State.PARTIAL:
        return "PARTIAL_SUCCESS"
    if state == State.ROLLED_BACK:
        return "ROLLED_BACK"
    if state == State.CANCELLED:
        return "CANCELLED"
    if state in (State.RUNNING, State.PUBLISHED):
        return "RUNNING"
    if state == State.VERIFYING:
        return "VERIFYING"
    if state == State.FINISH:
        return "SUCCEEDED"
    if state == State.FAILED:
        return "FAILED"
    if state in (State.APPROVED, State.PUBLISHED):
        return "RUNNING"
    return "PENDING"


def _severity_from_blockers(blockers: List[Dict]) -> str:
    return "MEDIUM" if blockers else "INFO"


def _severity_from_audit_summary(summary: Dict) -> str:
    if summary.get("permit_any_any_count", 0) or summary.get("high_risk_service_rule_count", 0):
        return "HIGH"
    if summary.get("logging_review_count", 0):
        return "MEDIUM"
    return "INFO"


def _extract_change_summary(kwargs_payload: Dict, task_result: Dict) -> Dict:
    return kwargs_payload.get("change_summary") or task_result.get("change_summary") or {}


def _serialize_device_facts(device: NetworkDevice) -> Dict:
    vendor = getattr(device, "vendor", None)
    category = getattr(device, "category", None)
    model = getattr(device, "model", None)
    plan = getattr(device, "plan", None)
    return {
        "id": getattr(device, "id", None),
        "serial_num": getattr(device, "serial_num", ""),
        "manage_ip": getattr(device, "manage_ip", ""),
        "name": getattr(device, "name", ""),
        "vendor_name": getattr(vendor, "name", ""),
        "vendor_alias": getattr(vendor, "alias", ""),
        "category_name": getattr(category, "name", ""),
        "model_name": getattr(model, "name", ""),
        "soft_version": getattr(device, "soft_version", ""),
        "patch_version": getattr(device, "patch_version", ""),
        "legacy_plan_name": getattr(plan, "name", ""),
    }


def _serialize_discovery_state(discovery_state: Optional[DeviceDiscoveryState]) -> Dict:
    if not discovery_state:
        return {}
    return {
        "profile_code": getattr(discovery_state, "profile_code", "") or "",
        "last_discovered_at": getattr(discovery_state, "last_discovered_at", None),
        "last_discovery_status": getattr(discovery_state, "last_discovery_status", "") or "",
        "last_discovery_error": getattr(discovery_state, "last_discovery_error", "") or "",
    }


class AgentDeviceFactsAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _get_device(serial_num: str):
        return (
            NetworkDevice.objects.select_related("vendor", "category", "model", "plan")
            .filter(serial_num=serial_num)
            .first()
        )

    def get(self, request, serial_num):
        device = self._get_device(serial_num)
        if not device:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "DEVICE_NOT_FOUND", "message": "device serial_num does not exist"},
                payload=None,
                http_status=404,
            )

        discovery_state = DeviceDiscoveryState.objects.filter(device_serial_num=serial_num).first()
        payload = {
            **_serialize_device_facts(device),
            **_serialize_discovery_state(discovery_state),
        }
        return _response(
            task_id=_now_task_id("facts"),
            execution_id=None,
            status="SUCCEEDED",
            severity="INFO",
            summary={
                "serial_num": payload["serial_num"],
                "vendor": payload.get("vendor_alias") or payload.get("vendor_name"),
                "profile_code": payload.get("profile_code", ""),
                "collected_from": "device_api",
            },
            artifacts=[
                {
                    "type": "facts_snapshot",
                    "ref": f"device-facts://{serial_num}",
                }
            ],
            payload=payload,
        )


class AgentDeviceCapabilitiesAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _get_device(serial_num: str):
        return (
            NetworkDevice.objects.select_related("vendor", "category", "model", "plan")
            .filter(serial_num=serial_num)
            .first()
        )

    @staticmethod
    def _get_blockers(device: NetworkDevice) -> List[Dict]:
        coverage = PlatformProfileService.audit_device_coverage([device])
        results = coverage.get("results", [])
        if not results:
            return [{"code": "profile_not_matched", "message": "设备未匹配到平台画像"}]
        return results[0].get("blockers", [])

    def get(self, request, serial_num):
        device = self._get_device(serial_num)
        if not device:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "DEVICE_NOT_FOUND", "message": "device serial_num does not exist"},
                payload=None,
                http_status=404,
            )

        capabilities = PlatformProfileService.build_capabilities(device)
        blockers = self._get_blockers(device)
        payload = {
            **capabilities,
            "blocking_reasons": blockers,
            "is_ready": not blockers,
        }
        return _response(
            task_id=_now_task_id("capabilities"),
            execution_id=None,
            status="SUCCEEDED",
            severity=_severity_from_blockers(blockers),
            summary={
                "serial_num": capabilities.get("serial_num", serial_num),
                "profile_code": capabilities.get("profile_code", ""),
                "supported_collection_types": capabilities.get("supported_collection_types", []),
                "is_ready": not blockers,
            },
            artifacts=[
                {
                    "type": "capabilities_profile",
                    "ref": f"device-capabilities://{serial_num}",
                }
            ],
            payload=payload,
        )


class AgentInspectionTaskAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _load_devices(serial_nums: List[str]):
        return list(
            NetworkDevice.objects.select_related("vendor", "category", "model", "plan")
            .filter(serial_num__in=serial_nums)
        )

    @staticmethod
    def _build_results(requested_serial_nums: List[str], devices: List[NetworkDevice]) -> Dict[str, object]:
        coverage = PlatformProfileService.audit_device_coverage(devices)
        coverage_results = {item.get("serial_num"): item for item in coverage.get("results", [])}
        ready = 0
        blocked = 0
        results = []

        for serial_num in requested_serial_nums:
            item = coverage_results.get(serial_num)
            if item is None:
                blocked += 1
                results.append(
                    {
                        "serial_num": serial_num,
                        "status": "blocked",
                        "blockers": [{"code": "device_not_found", "message": "设备不存在"}],
                    }
                )
                continue

            blockers = item.get("blockers", [])
            current_status = "success" if not blockers else "blocked"
            if blockers:
                blocked += 1
            else:
                ready += 1
            results.append(
                {
                    "serial_num": serial_num,
                    "manage_ip": item.get("manage_ip", ""),
                    "profile_code": item.get("profile_code", ""),
                    "plan_id": item.get("plan_id"),
                    "plan_name": item.get("plan_name", ""),
                    "status": current_status,
                    "blockers": blockers,
                }
            )

        return {"ready": ready, "blocked": blocked, "results": results}

    def post(self, request):
        serial_nums = request.data.get("serial_nums") or []
        serial_num = request.data.get("serial_num")
        if serial_num:
            serial_nums.append(serial_num)
        serial_nums = [item for item in dict.fromkeys(serial_nums) if item]
        if not serial_nums:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "INVALID_TARGET", "message": "serial_num or serial_nums is required"},
                http_status=400,
            )

        devices = self._load_devices(serial_nums)
        report = self._build_results(serial_nums, devices)
        task_id = request.data.get("task_id") or _now_task_id("inspect")
        inspection_type = request.data.get("inspection_type", "baseline")
        inspection_scope = request.data.get("inspection_scope") or ("device" if len(serial_nums) == 1 else "fleet")
        summary = {
            "task_type": "inspection_run",
            "inspection_type": inspection_type,
            "inspection_scope": inspection_scope,
            "target_count": len(serial_nums),
            "ready_count": report["ready"],
            "blocked_count": report["blocked"],
            "result": "partial" if report["ready"] and report["blocked"] else "success" if report["ready"] else "blocked",
        }

        if report["ready"] and report["blocked"]:
            status = "PARTIAL_SUCCESS"
            severity = "MEDIUM"
            workflow_state = State.FINISH
            code = 9008
        elif report["ready"]:
            status = "SUCCEEDED"
            severity = "INFO"
            workflow_state = State.FINISH
            code = 9008
        else:
            status = "FAILED"
            severity = "HIGH"
            workflow_state = State.FAILED
            code = 9005

        kwargs_payload = {
            "inspection_scope": inspection_scope,
            "inspection_type": inspection_type,
            "summary": summary,
        }
        execution = WorkflowExecution.objects.create(
            task_id=task_id,
            origin="NetClaw-CN",
            task_result=json.dumps({"summary": summary, "results": report["results"]}, ensure_ascii=False),
            order_code="",
            device=devices[0].manage_ip if len(devices) == 1 else None,
            device_id=getattr(devices[0], "id", None) if len(devices) == 1 else None,
            commit_user=getattr(getattr(request, "user", None), "username", "") or "system",
            commit_time=timezone.now(),
            task=Tasks.INSPECTION,
            method=Method.RESTAPI,
            class_method="agent_inspection_run",
            remote_ip=str(request.META.get("REMOTE_ADDR", "")),
            kwargs=json.dumps(kwargs_payload, ensure_ascii=False),
            ttp="{}",
            commands="[]",
            back_off_commands="[]",
            state=workflow_state,
            code=code,
        )

        return _response(
            task_id=task_id,
            execution_id=str(getattr(execution, "id", "")),
            status=status,
            severity=severity,
            summary=summary,
            artifacts=[
                {"type": "inspection_report", "ref": f"execution://inspection/{getattr(execution, 'id', '')}"},
                {"type": "inspection_results", "ref": f"inspection://{task_id}"},
            ],
            audit_ref=f"audit://inspection/{getattr(execution, 'id', '')}",
            payload={"results": report["results"]},
        )


class AgentExecutionDetailAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _get_execution(execution_id: int):
        return WorkflowExecution.objects.filter(id=execution_id).first()

    def get(self, request, execution_id):
        execution = self._get_execution(execution_id)
        if not execution:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "EXECUTION_NOT_FOUND", "message": "execution id does not exist"},
                http_status=404,
            )

        kwargs_payload = _parse_json(getattr(execution, "kwargs", "{}"), {})
        task_result = _parse_json(getattr(execution, "task_result", "{}"), {})
        summary = (
            _extract_change_summary(kwargs_payload, task_result)
            if getattr(execution, "task", "") == Tasks.CHANGE
            else kwargs_payload.get("summary") or task_result.get("summary") or {}
        )

        audit_ref = None
        rollback_ref = None
        if getattr(execution, "task", "") == Tasks.INSPECTION:
            audit_ref = f"audit://inspection/{execution_id}"
        elif getattr(execution, "task", "") == Tasks.SEC_POLICY:
            audit_record_id = kwargs_payload.get("audit_record_id")
            if audit_record_id:
                audit_ref = f"audit://security-policy/{audit_record_id}"
        elif getattr(execution, "task", "") == Tasks.CHANGE:
            audit_ref = kwargs_payload.get("audit_ref")
            rollback_ref = kwargs_payload.get("rollback_ref")

        return _response(
            task_id=getattr(execution, "task_id", ""),
            execution_id=str(execution_id),
            status=_workflow_status(getattr(execution, "state", "")),
            severity="MEDIUM" if summary.get("blocked_count") else "INFO",
            summary=summary,
            artifacts=[
                {"type": "execution_result", "ref": f"execution://{execution_id}"},
            ],
            audit_ref=audit_ref,
            rollback_ref=rollback_ref,
            payload={
                "task": getattr(execution, "task", ""),
                "method": getattr(execution, "method", ""),
                "state": getattr(execution, "state", ""),
                "inspection_payload": inspection_payload(execution) if getattr(execution, "task", "") == Tasks.INSPECTION else task_result,
                "inspection_summary": inspection_summary(execution) if getattr(execution, "task", "") == Tasks.INSPECTION else summary,
            },
        )


class AgentAnalysisAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _build_interface_items(request):
        queryset = InterfaceUtilizationSnapshot.objects.all().order_by("-snapshot_time")
        if request.GET.get("manage_ip"):
            queryset = queryset.filter(manage_ip=request.GET["manage_ip"])
        if request.GET.get("device_serial_num"):
            queryset = queryset.filter(device_serial_num=request.GET["device_serial_num"])
        limit = int(request.GET.get("limit", 20))
        items = list(queryset[:limit])
        latest_run = (
            AnalysisRun.objects.filter(run_kind=AnalysisRun.KIND_INTERFACE_UTILIZATION)
            .order_by("-created_at")
            .first()
        )
        payload_items = [
            {
                "device_serial_num": item.device_serial_num,
                "manage_ip": item.manage_ip,
                "component_scope": item.component_scope,
                "component_key": item.component_key,
                "component_name": item.component_name,
                "utilization_percent": item.utilization_percent,
                "source_execute_time": item.source_execute_time,
                "snapshot_time": item.snapshot_time,
            }
            for item in items
        ]
        summary = {
            "analysis_kind": "interface_utilization",
            "count": len(payload_items),
            "max_utilization_percent": max((item["utilization_percent"] for item in payload_items), default=0),
            "analysis_run_status": getattr(latest_run, "status", ""),
        }
        artifacts = [
            {"type": "analysis_run", "ref": f"analysis-run://{getattr(latest_run, 'id', '')}"}
        ] if latest_run else []
        artifacts.extend(
            [
                {"type": "source_execute_time", "ref": f"execute-time://{item['source_execute_time']}"}
                for item in payload_items
                if item.get("source_execute_time")
            ]
        )
        return summary, payload_items, artifacts

    @staticmethod
    def _build_address_items(request):
        queryset = AddressTraceSnapshot.objects.all().order_by("-observed_at")
        if request.GET.get("ip_address"):
            queryset = queryset.filter(ip_address=request.GET["ip_address"])
        if request.GET.get("manage_ip"):
            queryset = queryset.filter(manage_ip=request.GET["manage_ip"])
        limit = int(request.GET.get("limit", 20))
        items = list(queryset[:limit])
        latest_run = (
            AnalysisRun.objects.filter(run_kind=AnalysisRun.KIND_ADDRESS_TRACKING)
            .order_by("-created_at")
            .first()
        )
        payload_items = [
            {
                "ip_address": item.ip_address,
                "manage_ip": item.manage_ip,
                "device_serial_num": item.device_serial_num,
                "interface_name": item.interface_name,
                "trace_status": item.trace_status,
                "source_execute_time": item.source_execute_time,
                "observed_at": item.observed_at,
            }
            for item in items
        ]
        summary = {
            "analysis_kind": "address_tracking",
            "count": len(payload_items),
            "partial_count": sum(1 for item in payload_items if item["trace_status"] == AddressTraceSnapshot.STATUS_PARTIAL),
            "unresolved_count": sum(1 for item in payload_items if item["trace_status"] == AddressTraceSnapshot.STATUS_UNRESOLVED),
            "analysis_run_status": getattr(latest_run, "status", ""),
        }
        artifacts = [
            {"type": "analysis_run", "ref": f"analysis-run://{getattr(latest_run, 'id', '')}"}
        ] if latest_run else []
        artifacts.extend(
            [
                {"type": "source_execute_time", "ref": f"execute-time://{item['source_execute_time']}"}
                for item in payload_items
                if item.get("source_execute_time")
            ]
        )
        return summary, payload_items, artifacts

    def get(self, request):
        kind = request.GET.get("kind", "").strip()
        if kind == "interface_utilization":
            summary, payload_items, artifacts = self._build_interface_items(request)
        elif kind == "address_tracking":
            summary, payload_items, artifacts = self._build_address_items(request)
        else:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "INVALID_ANALYSIS_KIND", "message": "kind must be interface_utilization or address_tracking"},
                http_status=400,
            )

        return _response(
            task_id=_now_task_id("analysis"),
            execution_id=None,
            status="SUCCEEDED",
            severity="INFO",
            summary=summary,
            artifacts=artifacts,
            payload={"results": payload_items},
        )


class AgentSecurityAuditTaskAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    @staticmethod
    def _load_policies(device_ip: str, vendor: str):
        policies = sec_policy_mongo.find(query_dict=dict(hostip=device_ip), fields={"_id": 0})
        if vendor:
            vendor_aliases = get_vendor_aliases(vendor)
            policies = [item for item in policies if str(item.get("vendor", "")) in vendor_aliases]
        return policies

    def post(self, request):
        device_ip = request.data.get("device_ip") or request.data.get("hostip")
        vendor = request.data.get("vendor", "")
        if vendor:
            vendor = Vendor.normalize(vendor)

        if not device_ip:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "INVALID_TARGET", "message": "device_ip or hostip is required"},
                http_status=400,
            )

        task_id = request.data.get("task_id") or _now_task_id("security-audit")
        policies = self._load_policies(device_ip, vendor)
        audit_payload = build_sec_policy_audit_payload(
            policies=policies,
            hostip=device_ip,
            vendor=vendor,
        )
        summary = extract_sec_policy_audit_summary(audit_payload)
        findings = extract_sec_policy_findings(audit_payload)
        record = FirewallPolicyAuditRecord.objects.create(
            audit_type=FirewallPolicyAuditRecord.AuditType.SECURITY_POLICY,
            vendor=vendor or audit_payload.get("vendor", ""),
            device_ip=device_ip,
            operator=getattr(getattr(request, "user", None), "username", "") or "system",
            source="NetClaw-CN",
            status=FirewallPolicyAuditRecord.Status.SUCCESS,
            summary=summary,
            findings=findings,
            audit_payload=audit_payload,
            task_id=task_id,
        )
        execution = WorkflowExecution.objects.create(
            task_id=task_id,
            origin="NetClaw-CN",
            task_result=json.dumps({"summary": summary, "findings": findings}, ensure_ascii=False),
            order_code="",
            device=device_ip,
            device_id=None,
            commit_user=getattr(getattr(request, "user", None), "username", "") or "system",
            commit_time=timezone.now(),
            task=Tasks.SEC_POLICY,
            method=Method.RESTAPI,
            class_method="agent_security_policy_audit",
            remote_ip=str(request.META.get("REMOTE_ADDR", "")),
            kwargs=json.dumps({"device_ip": device_ip, "vendor": vendor, "audit_record_id": getattr(record, "id", None)}, ensure_ascii=False),
            ttp="{}",
            commands="[]",
            back_off_commands="[]",
            state=State.FINISH,
            code=9008,
        )

        return _response(
            task_id=task_id,
            execution_id=str(getattr(execution, "id", "")),
            status="SUCCEEDED",
            severity=_severity_from_audit_summary(summary),
            summary={
                "task_type": "security_audit_run",
                "vendor": vendor or audit_payload.get("vendor", ""),
                "device_ip": device_ip,
                **summary,
            },
            artifacts=[
                {"type": "audit_payload", "ref": f"audit-payload://security-policy/{getattr(record, 'id', '')}"},
                {"type": "findings", "ref": f"findings://security-policy/{getattr(record, 'id', '')}"},
            ],
            audit_ref=f"audit://security-policy/{getattr(record, 'id', '')}",
            payload={"summary": summary, "findings": findings, "result_count": len(findings)},
        )


class AgentChangeTaskAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    authentication_classes = (AgentRequestAuthentication,)

    REQUIRED_APPROVAL_STATUS = "approved"

    @staticmethod
    def _build_verify_result(request_data: Dict) -> Dict:
        verify_data = request_data.get("verify") or {}
        verify_passed = bool(verify_data.get("passed"))
        summary = {
            "verify_passed": verify_passed,
            "verify_type": verify_data.get("type", "post_change_check"),
            "verify_message": verify_data.get("message", ""),
        }
        return summary

    @staticmethod
    def _build_change_refs(task_id: str) -> Dict[str, str]:
        return {
            "baseline_ref": f"baseline://{task_id}",
            "verify_ref": f"verify://{task_id}",
            "rollback_ref": f"rollback://{task_id}",
            "audit_ref": f"audit://change/{task_id}",
        }

    def post(self, request):
        approval_status = (request.data.get("approval_status") or "").strip().lower()
        baseline_ref = (request.data.get("baseline_ref") or "").strip()
        change_template = (request.data.get("change_template") or "").strip()

        if approval_status != self.REQUIRED_APPROVAL_STATUS:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="HIGH",
                summary={"error_code": "APPROVAL_REQUIRED", "message": "change execution requires approved approval_status"},
                http_status=400,
            )
        if not baseline_ref:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="HIGH",
                summary={"error_code": "BASELINE_REQUIRED", "message": "baseline_ref is required before execution"},
                http_status=400,
            )
        if not change_template:
            return _response(
                task_id=None,
                execution_id=None,
                status="FAILED",
                severity="MEDIUM",
                summary={"error_code": "CHANGE_TEMPLATE_REQUIRED", "message": "change_template is required"},
                http_status=400,
            )

        task_id = request.data.get("task_id") or _now_task_id("change")
        refs = self._build_change_refs(task_id)
        verify_result = self._build_verify_result(request.data)
        rollback_requested = bool(request.data.get("rollback_requested", not verify_result["verify_passed"]))

        if verify_result["verify_passed"]:
            final_state = State.SUCCEEDED
            status = "SUCCEEDED"
            severity = "INFO"
            rollback_status = "not_needed"
            result_status = "verify_succeeded"
        elif rollback_requested:
            final_state = State.ROLLED_BACK
            status = "ROLLED_BACK"
            severity = "HIGH"
            rollback_status = "executed"
            result_status = "verify_failed_rolled_back"
        else:
            final_state = State.PARTIAL
            status = "PARTIAL_SUCCESS"
            severity = "HIGH"
            rollback_status = "pending_manual_confirmation"
            result_status = "verify_failed_pending_manual"

        change_summary = {
            "task_type": "change_run",
            "change_template": change_template,
            "approval_status": approval_status,
            "baseline_ref": baseline_ref,
            "verify_ref": refs["verify_ref"],
            "rollback_ref": refs["rollback_ref"],
            "verify_passed": verify_result["verify_passed"],
            "rollback_status": rollback_status,
            "result": result_status,
            "order_code": request.data.get("order_code", ""),
            "risk_level": request.data.get("risk_level", "medium"),
            "triggered_by": request.data.get("triggered_by", "agent"),
        }
        task_result = {
            "change_summary": change_summary,
            "baseline_ref": baseline_ref,
            "verify": verify_result,
            "rollback": {
                "requested": rollback_requested,
                "status": rollback_status,
                "message": request.data.get("rollback_message", ""),
            },
            "artifacts": request.data.get("artifacts", []),
        }
        kwargs_payload = {
            "change_summary": change_summary,
            "baseline_ref": baseline_ref,
            "verify_ref": refs["verify_ref"],
            "rollback_ref": refs["rollback_ref"],
            "audit_ref": refs["audit_ref"],
            "approval_status": approval_status,
        }
        execution = WorkflowExecution.objects.create(
            task_id=task_id,
            origin="NetClaw-CN",
            task_result=json.dumps(task_result, ensure_ascii=False),
            order_code=request.data.get("order_code", ""),
            device=request.data.get("device_ip"),
            device_id=request.data.get("device_id"),
            commit_user=getattr(getattr(request, "user", None), "username", "") or "system",
            commit_time=timezone.now(),
            task=Tasks.CHANGE,
            method=Method.RESTAPI,
            class_method="agent_change_run",
            remote_ip=str(request.META.get("REMOTE_ADDR", "")),
            kwargs=json.dumps(kwargs_payload, ensure_ascii=False),
            ttp="{}",
            commands=json.dumps(request.data.get("commands", []), ensure_ascii=False),
            back_off_commands=json.dumps(request.data.get("rollback_commands", []), ensure_ascii=False),
            state=final_state,
            code=9008 if final_state == State.SUCCEEDED else 9005,
        )
        artifacts = [
            {"type": "baseline", "ref": baseline_ref},
            {"type": "verify", "ref": refs["verify_ref"]},
            {"type": "change_execution", "ref": f"execution://change/{execution.id}"},
        ]
        if rollback_requested:
            artifacts.append({"type": "rollback", "ref": refs["rollback_ref"]})

        return _response(
            task_id=task_id,
            execution_id=str(execution.id),
            status=status,
            severity=severity,
            summary=change_summary,
            artifacts=artifacts,
            audit_ref=refs["audit_ref"],
            rollback_ref=refs["rollback_ref"],
            payload=task_result,
        )
