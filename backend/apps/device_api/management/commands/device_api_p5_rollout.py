import json
from datetime import datetime, timedelta
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.asset.models import NetworkDevice
from apps.device_api import (
    COLLECTION_PLAN,
    DEFAULT_COLLECTION_ENTRY,
    FALLBACK_COLLECTION_ENTRY,
)
from apps.device_api.tasks import plan_collect_device_main
from utils.db.mongo_ops import MongoOps


class Command(BaseCommand):
    help = "生成 P5 灰度替换/并行对比/回退演练报告，并可触发小流量灰度执行。"

    WAVE_VENDOR_ORDER = [
        {"wave": 1, "name": "Wave-1", "vendors": ["Huawei", "H3C"]},
        {"wave": 2, "name": "Wave-2", "vendors": ["Cisco", "Ruijie", "Hillstone"]},
        {"wave": 3, "name": "Wave-3", "vendors": ["ZTE", "Maipu", "Mellanox", "centec", "Centec"]},
    ]

    COMPARISON_COLLECTIONS = [
        ("arp", "plan_arp", "ARPTable"),
        ("mac", "plan_mac", "MACTable"),
        ("lldp", "plan_lldp", "LLDPTable"),
        ("interface_brief", "plan_interface_brief", "layer2interface"),
        ("ip_interface", "plan_ip_interface", "layer3interface"),
        ("aggre_port", "plan_aggre_port", "AggreTable"),
    ]

    LEGACY_TIME_FIELDS = [
        "execute_time",
        "log_time",
        "create_time",
        "collect_time",
        "createTime",
        "update_time",
    ]

    def add_arguments(self, parser):
        parser.add_argument("--wave", type=int, choices=[1, 2, 3], help="仅输出指定灰度波次")
        parser.add_argument("--execute-time", dest="execute_time", help="指定 device_api 批次 execute_time")
        parser.add_argument(
            "--manage-ip",
            dest="manage_ips",
            action="append",
            default=[],
            help="指定并行对比设备管理 IP，可重复传入；传入后不再按 wave 自动抽样",
        )
        parser.add_argument("--sample-limit", type=int, default=100, help="并行对比时抽样设备上限")
        parser.add_argument(
            "--comparison-mode",
            choices=["window", "strict"],
            default="window",
            help="并行对比模式：window=legacy 时间窗口聚合；strict=按 hostip+execute_time 精确对齐",
        )
        parser.add_argument(
            "--legacy-batch-field",
            default="execute_time",
            help="strict 模式下 legacy 批次锚点字段（默认 execute_time）",
        )
        parser.add_argument(
            "--legacy-window-minutes",
            type=int,
            default=180,
            help="legacy 对比窗口（分钟），围绕 execute_time 向前后扩展",
        )
        parser.add_argument("--legacy-start", help="legacy 对比窗口起始时间，优先级高于 --legacy-window-minutes")
        parser.add_argument("--legacy-end", help="legacy 对比窗口结束时间，优先级高于 --legacy-window-minutes")
        parser.add_argument("--skip-compare", action="store_true", help="跳过并行对比统计")
        parser.add_argument("--run-gray", action="store_true", help="触发指定波次的小流量灰度执行")
        parser.add_argument(
            "--gray-sample-limit",
            type=int,
            default=20,
            help="灰度执行按波次抽样设备上限，避免一次性下发全量任务",
        )
        parser.add_argument("--dry-run", action="store_true", help="仅输出报告，不执行灰度任务")
        parser.add_argument("--output", dest="output", help="将报告写入 JSON 文件")
        parser.add_argument("--evidence-dir", dest="evidence_dir", help="将 P5 证据文件写入目录")

        parser.add_argument("--drill-executed", action="store_true", help="标记本次包含实际回退演练")
        parser.add_argument("--drill-start", help="回退演练开始时间")
        parser.add_argument("--drill-end", help="回退演练结束时间")
        parser.add_argument("--drill-scope", default="", help="回退演练范围")
        parser.add_argument("--drill-operator", default="", help="回退演练执行人")
        parser.add_argument("--drill-result", choices=["pass", "fail"], default="pass", help="回退演练结果")
        parser.add_argument("--drill-notes", default="", help="回退演练备注")
        parser.add_argument(
            "--drill-verify-item",
            action="append",
            default=[],
            help="回退后验证项，可重复传入",
        )

        parser.add_argument("--release-owner", default="", help="发布负责人")
        parser.add_argument("--release-observer", default="", help="发布观察人")
        parser.add_argument("--release-rollback-owner", default="", help="回退负责人")
        parser.add_argument("--release-risk", default="medium", help="发布风险等级")
        parser.add_argument("--release-change", default="", help="发布变更说明")
        parser.add_argument(
            "--release-observation-item",
            action="append",
            default=[],
            help="发布后观察点，可重复传入",
        )

    @staticmethod
    def _latest_execute_time():
        cursor = COLLECTION_PLAN.coll.find({}, {"_id": 0, "execute_time": 1}).sort(
            [("execute_time", -1), ("log_time", -1)]
        ).limit(1)
        rows = list(cursor)
        if rows and rows[0].get("execute_time"):
            return rows[0]["execute_time"]
        return ""

    @staticmethod
    def _count_active_devices_by_vendor(vendors):
        return NetworkDevice.objects.filter(
            status=0,
            auto_enable=True,
            vendor__alias__in=vendors,
        ).count()

    @staticmethod
    def _sample_manage_ips_by_vendor(vendors, limit=100):
        return list(
            NetworkDevice.objects.filter(
                status=0,
                auto_enable=True,
                vendor__alias__in=vendors,
            )
            .values_list("manage_ip", flat=True)[: max(1, int(limit))]
        )

    @classmethod
    def _build_wave_plan(cls, wave=None):
        waves = []
        for item in cls.WAVE_VENDOR_ORDER:
            if wave and item["wave"] != wave:
                continue
            waves.append(
                {
                    **item,
                    "device_count": cls._count_active_devices_by_vendor(item["vendors"]),
                }
            )
        return waves

    @classmethod
    def _parse_datetime(cls, raw):
        if not raw:
            return None
        raw_text = str(raw).strip()
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]:
            try:
                return datetime.strptime(raw_text, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw_text)
        except ValueError:
            return None

    @classmethod
    def _build_legacy_time_scope(cls, execute_time, legacy_start=None, legacy_end=None, legacy_window_minutes=180):
        start_dt = cls._parse_datetime(legacy_start)
        end_dt = cls._parse_datetime(legacy_end)
        execute_dt = cls._parse_datetime(execute_time)
        window_minutes = max(1, int(legacy_window_minutes or 180))

        if start_dt and end_dt:
            source = "manual_range"
        elif execute_dt:
            start_dt = execute_dt - timedelta(minutes=window_minutes)
            end_dt = execute_dt + timedelta(minutes=window_minutes)
            source = "execute_time_window"
        else:
            return {
                "enabled": False,
                "source": "disabled",
                "reason": "execute_time_not_parseable",
            }

        return {
            "enabled": True,
            "source": source,
            "start": start_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "end": end_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "window_minutes": window_minutes,
            "legacy_time_fields": cls.LEGACY_TIME_FIELDS,
        }

    @classmethod
    def _build_parallel_comparison(
        cls,
        execute_time,
        manage_ips,
        legacy_time_scope,
        comparison_mode="window",
        legacy_batch_field="execute_time",
    ):
        if not execute_time or not manage_ips:
            return {
                "execute_time": execute_time,
                "sample_device_count": len(manage_ips),
                "comparison_mode": comparison_mode,
                "legacy_batch_anchor": {
                    "enabled": comparison_mode == "strict",
                    "field": legacy_batch_field,
                    "value": execute_time,
                },
                "legacy_time_scope": legacy_time_scope,
                "collections": [],
                "summary": {
                    "checked_collections": 0,
                    "matched_collections": 0,
                    "mismatch_collections": 0,
                },
                "diagnostics": {},
            }

        comparisons = []
        matched = 0
        strict_anchor_missing_collections = []
        strict_no_time_field_collections = []
        for collection_type, device_api_coll, legacy_coll in cls.COMPARISON_COLLECTIONS:
            device_api_mongo = MongoOps(db="Automation", coll=device_api_coll)
            legacy_mongo = MongoOps(db="Automation", coll=legacy_coll)

            device_api_count = device_api_mongo.coll.count_documents(
                {"hostip": {"$in": manage_ips}, "execute_time": execute_time}
            )
            legacy_query = {"hostip": {"$in": manage_ips}}
            anchor_non_null_count = None
            any_time_field_non_null_count = None
            if comparison_mode == "strict":
                legacy_query[legacy_batch_field] = execute_time
                anchor_non_null_count = legacy_mongo.coll.count_documents(
                    {
                        "hostip": {"$in": manage_ips},
                        legacy_batch_field: {"$exists": True, "$ne": None},
                    }
                )
                any_time_field_non_null_count = legacy_mongo.coll.count_documents(
                    {
                        "hostip": {"$in": manage_ips},
                        "$or": [
                            {field: {"$exists": True, "$ne": None}}
                            for field in cls.LEGACY_TIME_FIELDS
                        ],
                    }
                )
            elif legacy_time_scope.get("enabled"):
                start_text = legacy_time_scope.get("start")
                end_text = legacy_time_scope.get("end")
                start_dt = cls._parse_datetime(start_text)
                end_dt = cls._parse_datetime(end_text)
                legacy_query["$or"] = [
                    {
                        field: {
                            "$gte": start_text,
                            "$lte": end_text,
                        }
                    }
                    for field in legacy_time_scope.get("legacy_time_fields", [])
                ]
                if start_dt and end_dt:
                    legacy_query["$or"].extend(
                        [
                            {
                                field: {
                                    "$gte": start_dt,
                                    "$lte": end_dt,
                                }
                            }
                            for field in legacy_time_scope.get("legacy_time_fields", [])
                        ]
                    )
            legacy_count = legacy_mongo.coll.count_documents(legacy_query)
            gap = device_api_count - legacy_count
            is_match = device_api_count == legacy_count
            if is_match:
                matched += 1
            if comparison_mode == "strict" and legacy_count == 0:
                if (anchor_non_null_count or 0) == 0:
                    strict_anchor_missing_collections.append(legacy_coll)
                if (any_time_field_non_null_count or 0) == 0:
                    strict_no_time_field_collections.append(legacy_coll)
            comparisons.append(
                {
                    "collection_type": collection_type,
                    "device_api_collection": device_api_coll,
                    "legacy_collection": legacy_coll,
                    "device_api_count": device_api_count,
                    "legacy_count": legacy_count,
                    "count_gap": gap,
                    "is_match": is_match,
                    "legacy_query_has_time_scope": "$or" in legacy_query,
                    "legacy_anchor_non_null_count": anchor_non_null_count,
                    "legacy_any_time_field_non_null_count": any_time_field_non_null_count,
                }
            )

        total = len(comparisons)
        diagnostics = {}
        if comparison_mode == "strict":
            diagnostics = {
                "strict_anchor_missing_collections": sorted(set(strict_anchor_missing_collections)),
                "strict_no_time_field_collections": sorted(set(strict_no_time_field_collections)),
            }
            if strict_anchor_missing_collections:
                diagnostics["root_cause_hint"] = (
                    "legacy collections missing batch anchor field; strict comparison may be all-zero."
                )
        return {
            "execute_time": execute_time,
            "sample_device_count": len(manage_ips),
            "comparison_mode": comparison_mode,
            "legacy_batch_anchor": {
                "enabled": comparison_mode == "strict",
                "field": legacy_batch_field,
                "value": execute_time,
            },
            "legacy_time_scope": legacy_time_scope,
            "collections": comparisons,
            "summary": {
                "checked_collections": total,
                "matched_collections": matched,
                "mismatch_collections": max(0, total - matched),
            },
            "diagnostics": diagnostics,
        }

    @staticmethod
    def _fallback_drill_template():
        return {
            "goal": "证明在不修改 automation 代码逻辑前提下可回退",
            "steps": [
                "冻结 device_api 批次证据（batch_gate_metrics + parent_collection_list + device_traceability）",
                "保持 clear_history=False，按同范围执行 automation 采集入口",
                "对比 success_rate、空结果率、字段完整性和结果数量",
                "仅回退运行策略，不改 apps.automation/apps.device_api 代码",
                "回退后继续保留 device_api 数据用于复盘与修复验证",
            ],
            "pass_criteria": [
                "回退操作可在既定窗口内完成",
                "回退后采集成功率恢复到基线阈值",
                "不出现需要热修 automation 代码才能恢复的情况",
            ],
        }

    @staticmethod
    def _build_fallback_drill_record(options):
        executed = bool(options.get("drill_executed"))
        verify_items = options.get("drill_verify_item") or []
        if executed and not verify_items:
            verify_items = [
                "回退后 30 分钟内采集成功率恢复到基线阈值",
                "回退后空结果率未升高",
                "回退后 analysis hooks 无新增阻塞",
            ]
        return {
            "executed": executed,
            "start_time": options.get("drill_start") or "",
            "end_time": options.get("drill_end") or "",
            "scope": options.get("drill_scope") or "",
            "operator": options.get("drill_operator") or "",
            "result": options.get("drill_result") if executed else "not_run",
            "verify_items": verify_items,
            "notes": options.get("drill_notes") or "",
            "code_change_required": False,
            "fallback_entry": FALLBACK_COLLECTION_ENTRY,
        }

    @staticmethod
    def _build_release_notes(options):
        observation_items = options.get("release_observation_item") or []
        if not observation_items:
            observation_items = [
                "batch_gate_metrics success_rate",
                "协议失败分类与跳过原因",
                "analysis_hooks 批次触发状态",
            ]
        return {
            "change": options.get("release_change") or "默认主链切换到 device_api（automation 保留 fallback）",
            "risk": options.get("release_risk") or "medium",
            "owner": options.get("release_owner") or "",
            "observer": options.get("release_observer") or "",
            "rollback_owner": options.get("release_rollback_owner") or "",
            "rollback": "仅回退运行策略到 automation，保持代码不变",
            "observation_items": observation_items,
            "default_entry": DEFAULT_COLLECTION_ENTRY,
            "fallback_entry": FALLBACK_COLLECTION_ENTRY,
        }

    @staticmethod
    def _write_json(path, payload):
        output_path = Path(path).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def _run_gray_wave(self, wave_item, dry_run=False, gray_sample_limit=20):
        manage_ips = self._sample_manage_ips_by_vendor(
            wave_item["vendors"],
            limit=max(1, int(gray_sample_limit or 20)),
        )
        if not manage_ips:
            return {
                "executed": False,
                "reason": "no_sample_devices",
                "sample_manage_ips": [],
            }
        if dry_run:
            return {
                "executed": False,
                "reason": "dry_run",
                "sample_manage_ips": manage_ips,
                "kwargs": {
                    "vendor__alias__in": wave_item["vendors"],
                    "manage_ip__in": manage_ips,
                    "clear_history": False,
                },
            }
        result = plan_collect_device_main(
            **{
                "vendor__alias__in": wave_item["vendors"],
                "manage_ip__in": manage_ips,
                "clear_history": False,
            }
        )
        return {
            "executed": True,
            "reason": "scheduled",
            "sample_manage_ips": manage_ips,
            "result": result,
        }

    @staticmethod
    def _build_acceptance_gate(comparison, gray_execution, fallback_drill_record, release_notes):
        collections = comparison.get("collections", []) if isinstance(comparison, dict) else []
        has_nonzero_comparison_data = any(
            (item.get("device_api_count", 0) > 0 or item.get("legacy_count", 0) > 0)
            for item in collections
        )
        has_nonzero_device_api_data = any(item.get("device_api_count", 0) > 0 for item in collections)
        has_nonzero_legacy_data = any(item.get("legacy_count", 0) > 0 for item in collections)
        gray_executed = any(
            item.get("result", {}).get("executed")
            for item in (gray_execution or [])
        )
        fallback_executed = bool(fallback_drill_record.get("executed"))
        release_complete = all(
            [
                bool(release_notes.get("owner")),
                bool(release_notes.get("observer")),
                bool(release_notes.get("rollback_owner")),
                bool(release_notes.get("observation_items")),
            ]
        )

        checks = {
            "parallel_comparison_has_nonzero_data": has_nonzero_comparison_data,
            "device_api_comparison_has_nonzero_data": has_nonzero_device_api_data,
            "legacy_comparison_has_nonzero_data": has_nonzero_legacy_data,
            "gray_execution_recorded": gray_executed,
            "fallback_drill_executed": fallback_executed,
            "release_notes_complete": release_complete,
        }
        return {
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
        }

    def handle(self, *args, **options):
        wave = options.get("wave")
        execute_time = options.get("execute_time") or self._latest_execute_time()
        sample_limit = options.get("sample_limit") or 100
        legacy_window_minutes = options.get("legacy_window_minutes") or 180
        legacy_start = options.get("legacy_start")
        legacy_end = options.get("legacy_end")
        comparison_mode = options.get("comparison_mode") or "window"
        legacy_batch_field = options.get("legacy_batch_field") or "execute_time"
        skip_compare = options.get("skip_compare", False)
        run_gray = options.get("run_gray", False)
        gray_sample_limit = options.get("gray_sample_limit") or 20
        dry_run = options.get("dry_run", False)

        wave_plan = self._build_wave_plan(wave=wave)
        selected_manage_ips = sorted(set(options.get("manage_ips") or []))
        if not selected_manage_ips:
            for wave_item in wave_plan:
                selected_manage_ips.extend(
                    self._sample_manage_ips_by_vendor(wave_item["vendors"], limit=sample_limit)
                )
            selected_manage_ips = sorted(set(selected_manage_ips))[:sample_limit]

        legacy_time_scope = self._build_legacy_time_scope(
            execute_time=execute_time,
            legacy_start=legacy_start,
            legacy_end=legacy_end,
            legacy_window_minutes=legacy_window_minutes,
        )

        comparison = {}
        if not skip_compare:
            comparison = self._build_parallel_comparison(
                execute_time=execute_time,
                manage_ips=selected_manage_ips,
                legacy_time_scope=legacy_time_scope,
                comparison_mode=comparison_mode,
                legacy_batch_field=legacy_batch_field,
            )

        gray_execution = []
        if run_gray:
            for wave_item in wave_plan:
                gray_execution.append(
                    {
                        "wave": wave_item["wave"],
                        "name": wave_item["name"],
                        "result": self._run_gray_wave(
                            wave_item,
                            dry_run=dry_run,
                            gray_sample_limit=gray_sample_limit,
                        ),
                    }
                )

        fallback_drill_record = self._build_fallback_drill_record(options)
        release_notes = self._build_release_notes(options)
        acceptance_gate = self._build_acceptance_gate(
            comparison=comparison,
            gray_execution=gray_execution,
            fallback_drill_record=fallback_drill_record,
            release_notes=release_notes,
        )

        report = {
            "generated_at": datetime.now().isoformat(),
            "strategy": {
                "default_entry": DEFAULT_COLLECTION_ENTRY,
                "fallback_entry": FALLBACK_COLLECTION_ENTRY,
            },
            "execute_time": execute_time,
            "wave_plan": wave_plan,
            "parallel_comparison": comparison,
            "gray_execution": gray_execution,
            "fallback_drill_template": self._fallback_drill_template(),
            "fallback_drill_record": fallback_drill_record,
            "release_notes": release_notes,
            "acceptance_gate": acceptance_gate,
        }

        self.stdout.write(self.style.SUCCESS("P5 灰度/对比/回退报告生成完成"))
        self.stdout.write(
            f"default_entry={DEFAULT_COLLECTION_ENTRY} fallback_entry={FALLBACK_COLLECTION_ENTRY}"
        )
        self.stdout.write(f"execute_time={execute_time or '-'}")
        for item in wave_plan:
            self.stdout.write(
                f"wave={item['wave']} vendors={','.join(item['vendors'])} devices={item['device_count']}"
            )
        if comparison:
            summary = comparison.get("summary", {})
            self.stdout.write(
                "comparison: "
                f"mode={comparison.get('comparison_mode', 'window')} "
                f"checked={summary.get('checked_collections', 0)} "
                f"matched={summary.get('matched_collections', 0)} "
                f"mismatch={summary.get('mismatch_collections', 0)}"
            )
            batch_anchor = comparison.get("legacy_batch_anchor", {})
            if batch_anchor.get("enabled"):
                self.stdout.write(
                    "legacy_anchor: "
                    f"field={batch_anchor.get('field', '-')} "
                    f"value={batch_anchor.get('value', '-')}"
                )
            diagnostics = comparison.get("diagnostics", {})
            root_cause_hint = diagnostics.get("root_cause_hint")
            if root_cause_hint:
                self.stdout.write(f"comparison_hint: {root_cause_hint}")
            scope = comparison.get("legacy_time_scope", {})
            self.stdout.write(
                "legacy_scope: "
                f"enabled={scope.get('enabled')} "
                f"source={scope.get('source', '-')} "
                f"start={scope.get('start', '-')} "
                f"end={scope.get('end', '-')}"
            )
        self.stdout.write(
            "acceptance_gate: "
            f"status={acceptance_gate.get('status')} "
            f"parallel_nonzero={acceptance_gate.get('checks', {}).get('parallel_comparison_has_nonzero_data')} "
            f"device_api_nonzero={acceptance_gate.get('checks', {}).get('device_api_comparison_has_nonzero_data')} "
            f"legacy_nonzero={acceptance_gate.get('checks', {}).get('legacy_comparison_has_nonzero_data')} "
            f"gray_done={acceptance_gate.get('checks', {}).get('gray_execution_recorded')} "
            f"drill_done={acceptance_gate.get('checks', {}).get('fallback_drill_executed')} "
            f"release_ready={acceptance_gate.get('checks', {}).get('release_notes_complete')}"
        )

        output = options.get("output")
        if output:
            output_path = self._write_json(output, report)
            self.stdout.write(f"report written: {output_path}")

        evidence_dir = options.get("evidence_dir")
        if evidence_dir:
            evidence_root = Path(evidence_dir).expanduser()
            evidence_root.mkdir(parents=True, exist_ok=True)
            rollout_path = self._write_json(evidence_root / "p5_rollout_report.json", report)
            fallback_path = self._write_json(
                evidence_root / "p5_fallback_drill_record.json",
                fallback_drill_record,
            )
            release_path = self._write_json(
                evidence_root / "p5_release_notes.json",
                release_notes,
            )
            self.stdout.write(f"evidence written: {rollout_path}")
            self.stdout.write(f"evidence written: {fallback_path}")
            self.stdout.write(f"evidence written: {release_path}")
