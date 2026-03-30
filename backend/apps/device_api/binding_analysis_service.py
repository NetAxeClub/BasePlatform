from collections import Counter, defaultdict
from datetime import datetime
import time

from apps.asset.models import NetworkDevice
from apps.device_api import (
    COLLECTION_BINDING_ANALYSIS,
    COLLECTION_EXECUTION_LOG,
    COLLECTION_PLAN,
    COLLECTION_RESULTS_DB,
    COLLECTION_SUB_PLAN,
)
from apps.device_api.platform_profiles import PlatformProfileService


def _pick_latest_execute_time():
    latest_doc = COLLECTION_PLAN.coll.find_one({}, {"execute_time": 1}, sort=[("_id", -1)])
    return str((latest_doc or {}).get("execute_time") or "")


def _top_method_samples(log_docs, limit=3):
    method_counter = Counter()
    for doc in log_docs:
        method_name = (
            (doc.get("details") or {}).get("method_name")
            or doc.get("collection_method")
            or doc.get("collection_type")
            or "unknown"
        )
        method_counter[method_name] += 1
    return [name for name, _ in method_counter.most_common(limit)]


def _persist_binding_analysis_checklist(execute_time, summary, checklist_items):
    now_iso = datetime.now().isoformat()
    log_time = time.time()
    COLLECTION_BINDING_ANALYSIS.delete_many({"execute_time": execute_time})

    docs = [
        {
            "doc_type": "summary",
            "execute_time": execute_time,
            **summary,
            "created_at": now_iso,
            "log_time": log_time,
        }
    ]
    for item in checklist_items:
        docs.append(
            {
                "doc_type": "device",
                "execute_time": execute_time,
                **item,
                "has_recommendations": bool(item.get("recommendations")),
                "recommendation_codes": [
                    recommendation.get("code", "")
                    for recommendation in item.get("recommendations", [])
                    if recommendation.get("code")
                ],
                "created_at": now_iso,
                "log_time": log_time,
            }
        )

    if len(docs) == 1:
        COLLECTION_BINDING_ANALYSIS.insert_one(docs[0])
    else:
        COLLECTION_BINDING_ANALYSIS.insert_many(docs)


def _build_binding_analysis_recommendations(plan_doc, sub_docs, log_docs, audit_item):
    recommendations = []
    failed_logs = [doc for doc in log_docs if doc.get("status") == "failed"]
    error_texts = [
        " ".join(
            filter(
                None,
                [
                    str(doc.get("reason") or ""),
                    str(doc.get("error") or ""),
                    str((doc.get("details") or {}).get("method_name") or ""),
                ],
            )
        )
        for doc in failed_logs
    ]
    coverage_counter = Counter(
        str(doc.get("collection_type") or "")
        for doc in sub_docs
        if doc.get("coverage_issue")
    )
    blocker_map = {
        str(item.get("code") or ""): str(item.get("message") or "")
        for item in (audit_item or {}).get("blockers", [])
    }

    if plan_doc.get("task_status") == "running":
        recommendations.append(
            {
                "code": "stale_running_task",
                "message": "批次结束后设备任务仍处于 running，建议核对 Celery 回调或任务落库完整性。",
            }
        )

    if any("NETCONF账号信息不存在" in text for text in error_texts):
        recommendations.append(
            {
                "code": "missing_netconf_account",
                "message": "当前 PlansToDevice 绑定方案包含 NETCONF 子方案，但设备缺少 NETCONF 账号；建议补齐账号或调整方案。",
            }
        )

    if any(
        token in text
        for text in error_texts
        for token in (
            "Unexpected element",
            "Capability exchange timed out",
            "Could not open socket",
            "AuthenticationException",
        )
    ):
        recommendations.append(
            {
                "code": "netconf_protocol_mismatch",
                "message": "运行结果显示当前绑定方案中的 NETCONF 子方案与设备协议能力不匹配；建议在独立绑定分析环节评估是否切换到 CLI 方案。",
            }
        )

    textfsm_fail_logs = [
        doc
        for doc in failed_logs
        if "Textfsm 模板解析失败" in str(doc.get("reason") or "")
        or "Textfsm 模板解析失败" in str(doc.get("error") or "")
    ]
    if textfsm_fail_logs:
        recommendations.append(
            {
                "code": "textfsm_template_mismatch",
                "message": "CLI 解析存在 TextFSM 模板失配，主要命令: %s；建议修模板或从方案中下线对应子方案。"
                % ", ".join(_top_method_samples(textfsm_fail_logs)),
            }
        )

    empty_processed = {
        collection_type: count
        for collection_type, count in coverage_counter.items()
        if collection_type
    }
    if empty_processed:
        recommendations.append(
            {
                "code": "empty_processed_data_review",
                "message": "存在空处理结果子方案，主要类型: %s；建议确认协议是否未配置、命令输出为空或字段映射缺口。"
                % ", ".join(
                    f"{collection_type}={count}"
                    for collection_type, count in sorted(
                        empty_processed.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:5]
                ),
            }
        )

    for blocker_code, blocker_message in blocker_map.items():
        recommendations.append(
            {
                "code": blocker_code,
                "message": blocker_message,
            }
        )

    deduped = []
    seen_codes = set()
    for item in recommendations:
        code = item.get("code")
        if not code or code in seen_codes:
            continue
        seen_codes.add(code)
        deduped.append(item)
    return deduped


def analyze_collection_plan_bindings_service(
    execute_time="",
    max_devices=0,
    sample_limit=100,
    record_execution_event=None,
):
    execute_time = str(execute_time or "").strip() or _pick_latest_execute_time()
    if not execute_time:
        return {
            "execute_time": "",
            "analyzed_devices": 0,
            "devices_with_recommendations": 0,
            "reason": "missing_execute_time",
            "results": [],
        }

    plan_docs = COLLECTION_PLAN.find(
        {"execute_time": execute_time},
        fields={
            "_id": 0,
            "device_ip": 1,
            "device_name": 1,
            "task_status": 1,
            "plan_id": 1,
            "plan_name": 1,
            "failed_sub_plans": 1,
            "coverage_issue_sub_plans": 1,
            "skipped_sub_plans": 1,
            "failed_details": 1,
            "coverage_details": 1,
        },
    )
    issue_plan_docs = [
        doc
        for doc in plan_docs
        if doc.get("task_status") != "success"
        or int(doc.get("failed_sub_plans") or 0) > 0
        or int(doc.get("coverage_issue_sub_plans") or 0) > 0
        or int(doc.get("skipped_sub_plans") or 0) > 0
    ]
    issue_plan_docs.sort(
        key=lambda item: (
            int(item.get("failed_sub_plans") or 0),
            int(item.get("coverage_issue_sub_plans") or 0),
            int(item.get("skipped_sub_plans") or 0),
        ),
        reverse=True,
    )
    if max_devices:
        issue_plan_docs = issue_plan_docs[: max(int(max_devices), 0)]

    device_ips = [str(doc.get("device_ip") or "") for doc in issue_plan_docs if doc.get("device_ip")]
    if not device_ips:
        if record_execution_event:
            record_execution_event(
                event_scope="analysis",
                event_type="batch_plan_binding_analysis_finished",
                status="success",
                execute_time=execute_time,
                reason="no_issue_devices",
                details={"analyzed_devices": 0, "devices_with_recommendations": 0},
            )
        return {
            "execute_time": execute_time,
            "analyzed_devices": 0,
            "devices_with_recommendations": 0,
            "reason": "no_issue_devices",
            "results": [],
        }

    sub_docs = COLLECTION_SUB_PLAN.find(
        {"execute_time": execute_time, "device_ip": {"$in": device_ips}},
        fields={
            "_id": 0,
            "device_ip": 1,
            "collection_type": 1,
            "task_status": 1,
            "coverage_issue": 1,
            "coverage_reason": 1,
            "collection_method": 1,
            "method_name": 1,
        },
    )
    log_docs = COLLECTION_EXECUTION_LOG.find(
        {"execute_time": execute_time, "device_ip": {"$in": device_ips}},
        fields={
            "_id": 0,
            "device_ip": 1,
            "event_scope": 1,
            "event_type": 1,
            "status": 1,
            "reason": 1,
            "error": 1,
            "details": 1,
            "collection_method": 1,
            "collection_type": 1,
        },
    )
    test_docs = COLLECTION_RESULTS_DB.find(
        {"execute_time": execute_time, "device_ip": {"$in": device_ips}},
        fields={
            "_id": 0,
            "device_ip": 1,
            "collection_type": 1,
            "processed_status": 1,
            "processed_error": 1,
            "status": 1,
        },
    )

    sub_docs_by_ip = defaultdict(list)
    for doc in sub_docs:
        sub_docs_by_ip[str(doc.get("device_ip") or "")].append(doc)

    log_docs_by_ip = defaultdict(list)
    for doc in log_docs:
        log_docs_by_ip[str(doc.get("device_ip") or "")].append(doc)

    test_docs_by_ip = defaultdict(list)
    for doc in test_docs:
        test_docs_by_ip[str(doc.get("device_ip") or "")].append(doc)

    devices = list(
        NetworkDevice.objects.filter(manage_ip__in=device_ips).select_related(
            "vendor",
            "category",
            "model",
            "ssh_account",
            "netconf_account",
        )
    )
    audit_result = PlatformProfileService.audit_device_coverage(devices)
    audit_result_map = {
        str(item.get("manage_ip") or ""): item for item in audit_result.get("results", [])
    }

    recommendation_counter = Counter()
    coverage_reason_counter = Counter()
    devices_with_recommendations = 0
    checklist_items = []
    results = []
    sample_limit = max(int(sample_limit or 0), 0)

    for plan_doc in issue_plan_docs:
        device_ip = str(plan_doc.get("device_ip") or "")
        device_sub_docs = sub_docs_by_ip.get(device_ip, [])
        device_log_docs = log_docs_by_ip.get(device_ip, [])
        device_test_docs = test_docs_by_ip.get(device_ip, [])
        audit_item = audit_result_map.get(device_ip, {})
        recommendations = _build_binding_analysis_recommendations(
            plan_doc,
            device_sub_docs,
            device_log_docs,
            audit_item,
        )

        for sub_doc in device_sub_docs:
            if sub_doc.get("coverage_issue"):
                coverage_reason_counter[str(sub_doc.get("coverage_reason") or "coverage_issue")] += 1
        for item in recommendations:
            recommendation_counter[item["code"]] += 1
        if recommendations:
            devices_with_recommendations += 1

        if recommendations and record_execution_event:
            record_execution_event(
                event_scope="device",
                event_type="binding_analysis_suggested",
                status="warning",
                severity="warning",
                execute_time=execute_time,
                device_info={"manage_ip": device_ip, "device_name": plan_doc.get("device_name", "")},
                reason=recommendations[0]["code"],
                details={
                    "task_status": plan_doc.get("task_status", ""),
                    "failed_sub_plans": int(plan_doc.get("failed_sub_plans") or 0),
                    "coverage_issue_sub_plans": int(plan_doc.get("coverage_issue_sub_plans") or 0),
                    "recommendation_codes": [item["code"] for item in recommendations[:8]],
                    "test_collection_errors": [
                        {
                            "collection_type": item.get("collection_type", ""),
                            "processed_status": item.get("processed_status", ""),
                            "processed_error": item.get("processed_error", ""),
                        }
                        for item in device_test_docs
                        if item.get("processed_error")
                    ][:5],
                },
            )

        checklist_item = {
            "device_ip": device_ip,
            "device_name": plan_doc.get("device_name", ""),
            "task_status": plan_doc.get("task_status", ""),
            "plan_id": plan_doc.get("plan_id"),
            "plan_name": plan_doc.get("plan_name", ""),
            "failed_sub_plans": int(plan_doc.get("failed_sub_plans") or 0),
            "coverage_issue_sub_plans": int(plan_doc.get("coverage_issue_sub_plans") or 0),
            "coverage_reasons": dict(
                Counter(
                    str(item.get("coverage_reason") or "coverage_issue")
                    for item in device_sub_docs
                    if item.get("coverage_issue")
                )
            ),
            "audit_blockers": (audit_item or {}).get("blockers", []),
            "recommendations": recommendations,
        }
        checklist_items.append(checklist_item)

        if sample_limit == 0 or len(results) < sample_limit:
            results.append(checklist_item)

    summary = {
        "execute_time": execute_time,
        "analyzed_devices": len(issue_plan_docs),
        "devices_with_recommendations": devices_with_recommendations,
        "recommendation_summary": dict(recommendation_counter),
        "coverage_reason_summary": dict(coverage_reason_counter),
        "stored_checklist_items": len(checklist_items),
        "sampled_results": len(results),
    }
    _persist_binding_analysis_checklist(execute_time, summary, checklist_items)
    if record_execution_event:
        record_execution_event(
            event_scope="analysis",
            event_type="batch_plan_binding_analysis_finished",
            status="success",
            execute_time=execute_time,
            details=summary,
        )
    return {
        **summary,
        "results": results,
    }
