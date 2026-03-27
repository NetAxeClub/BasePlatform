from collections import OrderedDict

from django.core.management.base import BaseCommand

from apps.asset.models import NetworkDevice
from apps.device_api.platform_profiles import PlatformProfileService
from apps.device_api.services_new import DeviceCollectionService


class Command(BaseCommand):
    help = "对 Huawei/H3C 现网设备执行 capability discovery，并按能力评分重新收敛默认采集方案绑定。"
    DEFAULT_DISCOVERY_CONNECTION_POLICY = {
        "netconf_timeout_seconds": 8,
        "netconf_retry_times": 0,
        "netmiko_timeout_seconds": 8,
        "netmiko_session_timeout_seconds": 15,
        "netmiko_retry_times": 0,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--vendor-alias",
            action="append",
            dest="vendor_aliases",
            default=[],
            help="仅处理指定厂商，可重复传入；默认 Huawei + H3C",
        )
        parser.add_argument("--manage-ip", dest="manage_ip", help="仅处理指定管理 IP")
        parser.add_argument("--serial-num", dest="serial_num", help="仅处理指定序列号")
        parser.add_argument("--limit", type=int, default=0, help="仅处理前 N 台设备")
        parser.add_argument(
            "--heartbeat-every",
            type=int,
            default=25,
            help="每 N 台输出一次 discovery 进度心跳",
        )
        parser.add_argument("--skip-rebind", action="store_true", help="仅刷新 capability，不执行 auto_bind")

    @staticmethod
    def _iter_capability_subplans(plan, vendor_alias):
        collection_types = ["netconf_capability"]
        if vendor_alias == "H3C":
            collection_types.append("cli_output_capability")
        for collection_type in collection_types:
            sub_plan = plan.collect_plans.filter(collection_type=collection_type).first()
            if sub_plan:
                yield sub_plan

    @staticmethod
    def _build_probe_summary():
        return {
            "total": 0,
            "probed_devices": 0,
            "probe_success": 0,
            "probe_failed": 0,
            "probe_skipped": 0,
        }

    @classmethod
    def _build_vendor_summaries(cls, vendor_aliases):
        return OrderedDict(
            (vendor_alias, cls._build_probe_summary()) for vendor_alias in vendor_aliases
        )

    @staticmethod
    def _normalize_vendor_alias(device):
        vendor_alias = getattr(getattr(device, "vendor", None), "alias", "")
        return str(vendor_alias or "").strip() or "UNKNOWN"

    @staticmethod
    def _format_probe_summary(prefix, summary):
        return (
            f"{prefix} total={summary['total']} "
            f"probed_devices={summary['probed_devices']} "
            f"probe_success={summary['probe_success']} "
            f"probe_failed={summary['probe_failed']} "
            f"probe_skipped={summary['probe_skipped']}"
        )

    def _write_discovery_summary(self, phase, summary):
        self.stdout.write(self._format_probe_summary(f"phase=discovery {phase}", summary))
        for vendor_alias, vendor_summary in summary["vendors"].items():
            self.stdout.write(
                self._format_probe_summary(
                    f"phase=discovery {phase} vendor={vendor_alias}",
                    vendor_summary,
                    )
            )

    @classmethod
    def _build_discovery_connection_policy(cls, device):
        policy = dict(cls.DEFAULT_DISCOVERY_CONNECTION_POLICY)
        vendor_alias = cls._normalize_vendor_alias(device)
        model_name = str(getattr(getattr(device, "model", None), "name", "") or "").upper()
        if vendor_alias == "H3C" and model_name.startswith("S5130"):
            policy["netconf_timeout_seconds"] = 5
        return policy

    def handle(self, *args, **options):
        vendor_aliases = options.get("vendor_aliases") or ["Huawei", "H3C"]
        heartbeat_every = max(int(options.get("heartbeat_every") or 25), 1)
        queryset = NetworkDevice.objects.filter(
            status=0,
            auto_enable=True,
            vendor__alias__in=vendor_aliases,
        ).select_related("vendor", "category", "model", "netconf_account", "ssh_account")

        manage_ip = options.get("manage_ip")
        serial_num = options.get("serial_num")
        limit = int(options.get("limit") or 0)

        if manage_ip:
            queryset = queryset.filter(manage_ip=manage_ip)
        if serial_num:
            queryset = queryset.filter(serial_num=serial_num)
        if limit > 0:
            queryset = queryset[:limit]

        devices = list(queryset)
        profiles = {profile.code: profile for profile in PlatformProfileService.ensure_builtin_profiles()}

        summary = {
            **self._build_probe_summary(),
            "total": len(devices),
            "vendors": self._build_vendor_summaries(vendor_aliases),
            "rebind": None,
        }
        samples = []

        for index, device in enumerate(devices, 1):
            vendor_alias = self._normalize_vendor_alias(device)
            vendor_summary = summary["vendors"].setdefault(vendor_alias, self._build_probe_summary())
            vendor_summary["total"] += 1
            profile = PlatformProfileService.match_profile_for_device(device, profiles=list(profiles.values()))
            if not profile:
                summary["probe_skipped"] += 1
                vendor_summary["probe_skipped"] += 1
                samples.append(
                    {
                        "manage_ip": device.manage_ip,
                        "serial_num": device.serial_num,
                        "status": "skipped",
                        "reason": "profile_not_matched",
                    }
                )
                continue

            plan = PlatformProfileService.ensure_default_plan_for_profile(profile)
            device_probe_success = False
            device_probe_failed = False
            probe_details = []

            for sub_plan in self._iter_capability_subplans(plan, profile.vendor_alias):
                if sub_plan.collection_type == "netconf_capability":
                    if not (device.netconf_enable == "account" and device.netconf_account):
                        probe_details.append(
                            {
                                "collection_type": sub_plan.collection_type,
                                "status": "skipped",
                                "reason": "missing_netconf_account",
                            }
                        )
                        continue
                if sub_plan.collection_type == "cli_output_capability":
                    if not (device.ssh_enable == "account" and device.ssh_account):
                        probe_details.append(
                            {
                                "collection_type": sub_plan.collection_type,
                                "status": "skipped",
                                "reason": "missing_ssh_account",
                            }
                        )
                        continue

                result = DeviceCollectionService.execute_both_collection_local(
                    sub_plan,
                    device,
                    connection_policy=self._build_discovery_connection_policy(device),
                )
                if result.get("success"):
                    device_probe_success = True
                    summary["probe_success"] += 1
                    vendor_summary["probe_success"] += 1
                    probe_details.append({"collection_type": sub_plan.collection_type, "status": "success"})
                else:
                    device_probe_failed = True
                    summary["probe_failed"] += 1
                    vendor_summary["probe_failed"] += 1
                    if (
                        vendor_alias == "H3C"
                        and sub_plan.collection_type == "netconf_capability"
                    ):
                        PlatformProfileService.record_capability_probe_failure(
                            device_info={
                                "manage_ip": device.manage_ip,
                                "serial_num": device.serial_num,
                            },
                            collection_type="netconf_capability",
                            error=result.get("error", ""),
                            rebind_on_failure=False,
                        )
                    probe_details.append(
                        {
                            "collection_type": sub_plan.collection_type,
                            "status": "failed",
                            "error": result.get("error", ""),
                        }
                    )

            if device_probe_success or device_probe_failed:
                summary["probed_devices"] += 1
                vendor_summary["probed_devices"] += 1
            else:
                summary["probe_skipped"] += 1
                vendor_summary["probe_skipped"] += 1

            if len(samples) < 20:
                samples.append(
                    {
                        "manage_ip": device.manage_ip,
                        "serial_num": device.serial_num,
                        "profile_code": profile.code,
                        "plan_name": plan.name,
                        "probes": probe_details,
                    }
                )

            if index % heartbeat_every == 0 or index == len(devices):
                self._write_discovery_summary(
                    phase=f"heartbeat progress={index}/{len(devices)}",
                    summary=summary,
                )

        self._write_discovery_summary(phase="summary", summary=summary)

        if not options.get("skip_rebind"):
            summary["rebind"] = PlatformProfileService.auto_bind_devices(devices)
            self.stdout.write(
                self.style.SUCCESS(
                    "phase=auto_bind summary "
                    f"created={summary['rebind']['created']} "
                    f"updated={summary['rebind']['updated']} "
                    f"retired={summary['rebind']['retired']}"
                )
            )
            self.stdout.write(f"phase=auto_bind skipped={summary['rebind']['skipped']}")

        self.stdout.write(self.style.SUCCESS("capability discovery finished"))
        self.stdout.write(str(summary))
        for item in samples:
            self.stdout.write(str(item))
