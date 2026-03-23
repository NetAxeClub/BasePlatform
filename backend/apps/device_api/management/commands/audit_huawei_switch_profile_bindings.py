import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.asset.models import NetworkDevice
from apps.device_api.models import PlansToDevice
from apps.device_api.platform_profiles import PlatformProfileService


class Command(BaseCommand):
    help = "审计 Huawei 交换机当前平台画像/默认方案绑定是否与运行时判型一致，并可修正自动绑定。"

    def add_arguments(self, parser):
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅审计指定管理 IP")
        parser.add_argument("--serial-num", dest="serial_num", help="仅审计指定序列号")
        parser.add_argument("--limit", type=int, default=0, help="仅审计前 N 台设备")
        parser.add_argument("--sample-limit", type=int, default=20, help="输出样例数量上限")
        parser.add_argument("--fix-auto-bind", action="store_true", help="对可安全修正的设备执行 auto_bind")
        parser.add_argument(
            "--fix-empty-manual-conflicts",
            action="store_true",
            help="对已存在正确 auto 绑定的设备，退役空的 manual/legacy 活跃绑定",
        )
        parser.add_argument("--output", dest="output", help="将完整审计结果写入 JSON 文件")

    @staticmethod
    def _collect_active_bindings(device):
        queryset = PlansToDevice.objects.filter(is_active=True).select_related("plan")
        if getattr(device, "serial_num", ""):
            queryset = queryset.filter(device_serial_num=device.serial_num)
        else:
            queryset = queryset.filter(manage_ip=device.manage_ip)
        return list(queryset.order_by("-updated_at", "-id"))

    @classmethod
    def _group_active_bindings(cls, devices):
        serial_nums = [str(getattr(device, "serial_num", "") or "").strip() for device in devices]
        serial_nums = [item for item in serial_nums if item]
        manage_ips = [str(getattr(device, "manage_ip", "") or "").strip() for device in devices]
        manage_ips = [item for item in manage_ips if item]
        if not serial_nums and not manage_ips:
            return {}

        queryset = PlansToDevice.objects.filter(is_active=True).select_related("plan")
        if serial_nums and manage_ips:
            queryset = queryset.filter(Q(device_serial_num__in=serial_nums) | Q(manage_ip__in=manage_ips))
        elif serial_nums:
            queryset = queryset.filter(device_serial_num__in=serial_nums)
        else:
            queryset = queryset.filter(manage_ip__in=manage_ips)

        grouped = {}
        for binding in queryset.order_by("device_serial_num", "manage_ip", "-updated_at", "-id"):
            keys = [str(getattr(binding, "device_serial_num", "") or "").strip(), str(getattr(binding, "manage_ip", "") or "").strip()]
            for key in keys:
                if key:
                    grouped.setdefault(key, []).append(binding)
        return grouped

    @staticmethod
    def _resolve_binding_profile_code(binding):
        if not binding:
            return ""
        plan = getattr(binding, "plan", None)
        return str(
            getattr(binding, "profile_code", "")
            or getattr(plan, "profile_code", "")
            or ""
        ).strip()

    @classmethod
    def _build_binding_payload(cls, binding):
        plan = getattr(binding, "plan", None)
        return {
            "binding_id": getattr(binding, "id", None),
            "plan_id": getattr(binding, "plan_id", None),
            "plan_name": getattr(plan, "name", ""),
            "profile_code": cls._resolve_binding_profile_code(binding),
            "binding_source": getattr(binding, "binding_source", ""),
            "use_local": getattr(binding, "use_local", None),
            "execute_node": getattr(binding, "execute_node", ""),
        }

    @classmethod
    def _binding_plan_name(cls, binding):
        return str(getattr(getattr(binding, "plan", None), "name", "") or "").strip()

    @classmethod
    def _binding_matches_expected(cls, binding, expected_profile):
        if not binding or not expected_profile:
            return False
        return (
            cls._resolve_binding_profile_code(binding) == expected_profile.code
            and cls._binding_plan_name(binding) == expected_profile.default_plan_name
        )

    @classmethod
    def _is_empty_non_auto_binding(cls, binding):
        if not binding or getattr(binding, "binding_source", "") == PlansToDevice.BINDING_SOURCE_AUTO:
            return False
        return not getattr(binding, "plan_id", None) and not cls._resolve_binding_profile_code(binding)

    @staticmethod
    def _retire_bindings(bindings):
        binding_ids = [getattr(binding, "id", None) for binding in bindings if getattr(binding, "id", None)]
        if not binding_ids:
            return {"devices": 0, "retired_bindings": 0, "binding_ids": []}
        retired_count = PlansToDevice.objects.filter(id__in=binding_ids, is_active=True).update(is_active=False)
        return {
            "devices": 0,
            "retired_bindings": retired_count,
            "binding_ids": binding_ids,
        }

    def handle(self, *args, **options):
        queryset = NetworkDevice.objects.filter(
            status=0,
            auto_enable=True,
            vendor__alias="Huawei",
        ).select_related("vendor", "category", "model")
        manage_ip = options.get("manage_ip")
        serial_num = options.get("serial_num")
        limit = int(options.get("limit") or 0)
        sample_limit = max(int(options.get("sample_limit") or 20), 1)

        if manage_ip:
            queryset = queryset.filter(manage_ip=manage_ip)
        if serial_num:
            queryset = queryset.filter(serial_num=serial_num)
        if limit > 0:
            queryset = queryset[:limit]

        devices = [
            device
            for device in queryset
            if PlatformProfileService.normalize_device_category(
                getattr(getattr(device, "category", None), "name", "")
            ) == "switch"
        ]
        profiles = [
            profile
            for profile in PlatformProfileService.ensure_builtin_profiles()
            if profile.vendor_alias == "Huawei" and profile.category == "switch"
        ]

        summary = {
            "total": len(devices),
            "matched": 0,
            "profile_not_matched": 0,
            "missing_binding": 0,
            "profile_mismatch": 0,
            "plan_mismatch": 0,
            "multiple_active_bindings": 0,
            "manual_binding_conflict": 0,
            "fix_candidates": 0,
            "empty_manual_cleanup_candidates": 0,
        }
        results = []
        fix_candidates = []
        empty_manual_cleanup_candidates = []
        binding_map = self._group_active_bindings(devices)

        for device in devices:
            expected_profile = PlatformProfileService.match_profile_for_device(
                device,
                profiles=profiles,
            )
            device_key = str(getattr(device, "serial_num", "") or "").strip() or str(getattr(device, "manage_ip", "") or "").strip()
            active_bindings = list(binding_map.get(device_key, []))
            binding_payloads = [self._build_binding_payload(item) for item in active_bindings]
            issues = []
            primary_binding = active_bindings[0] if active_bindings else None

            item = {
                "manage_ip": getattr(device, "manage_ip", ""),
                "serial_num": getattr(device, "serial_num", ""),
                "device_name": getattr(device, "name", ""),
                "model_name": getattr(getattr(device, "model", None), "name", "") or "",
                "expected_profile_code": expected_profile.code if expected_profile else "",
                "expected_plan_name": expected_profile.default_plan_name if expected_profile else "",
                "active_bindings": binding_payloads,
                "issues": issues,
            }

            if not expected_profile:
                summary["profile_not_matched"] += 1
                issues.append("profile_not_matched")

            if not active_bindings:
                summary["missing_binding"] += 1
                issues.append("missing_binding")

            if len(active_bindings) > 1:
                summary["multiple_active_bindings"] += 1
                issues.append("multiple_active_bindings")

            if expected_profile and primary_binding:
                current_profile_code = self._resolve_binding_profile_code(primary_binding)
                current_plan_name = self._binding_plan_name(primary_binding)
                if current_profile_code != expected_profile.code:
                    summary["profile_mismatch"] += 1
                    issues.append("profile_mismatch")
                if current_plan_name != expected_profile.default_plan_name:
                    summary["plan_mismatch"] += 1
                    issues.append("plan_mismatch")

                manual_conflict = any(
                    getattr(binding, "binding_source", "") != PlansToDevice.BINDING_SOURCE_AUTO
                    and (
                        self._resolve_binding_profile_code(binding) != expected_profile.code
                        or getattr(getattr(binding, "plan", None), "name", "") != expected_profile.default_plan_name
                    )
                    for binding in active_bindings
                )
                if manual_conflict:
                    summary["manual_binding_conflict"] += 1
                    issues.append("manual_binding_conflict")

                non_auto_bindings = [
                    binding for binding in active_bindings
                    if getattr(binding, "binding_source", "") != PlansToDevice.BINDING_SOURCE_AUTO
                ]
                matching_auto_binding = next(
                    (
                        binding for binding in active_bindings
                        if getattr(binding, "binding_source", "") == PlansToDevice.BINDING_SOURCE_AUTO
                        and self._binding_matches_expected(binding, expected_profile)
                    ),
                    None,
                )
                safe_empty_manual_bindings = [
                    binding for binding in non_auto_bindings
                    if self._is_empty_non_auto_binding(binding)
                ]
                safe_empty_manual_cleanup = bool(
                    matching_auto_binding
                    and non_auto_bindings
                    and safe_empty_manual_bindings
                    and len(safe_empty_manual_bindings) == len(non_auto_bindings)
                )
                if safe_empty_manual_cleanup:
                    summary["empty_manual_cleanup_candidates"] += 1
                    item["recommended_action"] = "retire_empty_manual_bindings"
                    item["cleanup_binding_ids"] = [
                        getattr(binding, "id", None) for binding in safe_empty_manual_bindings
                    ]
                    empty_manual_cleanup_candidates.append(
                        {
                            "device": device,
                            "bindings": safe_empty_manual_bindings,
                        }
                    )

            if not issues:
                summary["matched"] += 1
            else:
                # auto_bind 只能安全覆盖缺失绑定或已有 auto 绑定偏移，手工/legacy 偏移只做提示
                fixable = (
                    expected_profile is not None
                    and "manual_binding_conflict" not in issues
                    and any(
                        issue in {"missing_binding", "profile_mismatch", "plan_mismatch", "multiple_active_bindings"}
                        for issue in issues
                    )
                )
                if fixable:
                    summary["fix_candidates"] += 1
                    fix_candidates.append(device)

            results.append(item)

        fix_result = None
        if options.get("fix_auto_bind") and fix_candidates:
            fix_result = PlatformProfileService.auto_bind_devices(fix_candidates)

        manual_cleanup_result = None
        if options.get("fix_empty_manual_conflicts") and empty_manual_cleanup_candidates:
            cleanup_bindings = []
            for candidate in empty_manual_cleanup_candidates:
                cleanup_bindings.extend(candidate["bindings"])
            manual_cleanup_result = self._retire_bindings(cleanup_bindings)
            manual_cleanup_result["devices"] = len(empty_manual_cleanup_candidates)

        payload = {
            "summary": summary,
            "results": results,
            "fix_result": fix_result,
            "manual_cleanup_result": manual_cleanup_result,
        }

        self.stdout.write(self.style.SUCCESS("Huawei 交换机画像绑定审计完成"))
        self.stdout.write(
            "summary: "
            f"total={summary['total']} matched={summary['matched']} "
            f"profile_not_matched={summary['profile_not_matched']} "
            f"missing_binding={summary['missing_binding']} "
            f"profile_mismatch={summary['profile_mismatch']} "
            f"plan_mismatch={summary['plan_mismatch']} "
            f"multiple_active_bindings={summary['multiple_active_bindings']} "
            f"manual_binding_conflict={summary['manual_binding_conflict']} "
            f"fix_candidates={summary['fix_candidates']} "
            f"empty_manual_cleanup_candidates={summary['empty_manual_cleanup_candidates']}"
        )

        issue_items = [item for item in results if item["issues"]]
        if not issue_items:
            self.stdout.write("issue samples: none")
        else:
            self.stdout.write("issue samples:")
            for item in issue_items[:sample_limit]:
                self.stdout.write(
                    f"- {item['manage_ip']} serial={item['serial_num']} "
                    f"expected={item['expected_profile_code'] or '-'} "
                    f"issues={','.join(item['issues'])}"
                )

        if fix_result:
            self.stdout.write(
                self.style.SUCCESS(
                    "fix_auto_bind: "
                    f"created={fix_result['created']} "
                    f"updated={fix_result['updated']} "
                    f"skipped={fix_result['skipped']} "
                    f"retired={fix_result['retired']}"
                )
            )
        elif options.get("fix_auto_bind"):
            self.stdout.write("fix_auto_bind: no eligible devices")

        if manual_cleanup_result:
            self.stdout.write(
                self.style.SUCCESS(
                    "fix_empty_manual_conflicts: "
                    f"devices={manual_cleanup_result['devices']} "
                    f"retired_bindings={manual_cleanup_result['retired_bindings']}"
                )
            )
        elif options.get("fix_empty_manual_conflicts"):
            self.stdout.write("fix_empty_manual_conflicts: no eligible devices")

        output = options.get("output")
        if output:
            output_path = Path(output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self.stdout.write(f"report written: {output_path}")
