import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.asset.models import NetworkDevice
from utils.db.mongo_ops import MongoOps


class Command(BaseCommand):
    help = "审计 legacy 结果表的批次锚点与时间字段覆盖率，并输出发布前门禁结论。"

    LEGACY_COLLECTIONS = [
        "ARPTable",
        "MACTable",
        "LLDPTable",
        "layer2interface",
        "layer3interface",
        "AggreTable",
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
        parser.add_argument(
            "--manage-ip",
            dest="manage_ips",
            action="append",
            default=[],
            help="指定设备管理 IP，可重复传入；为空时按在线纳管设备抽样",
        )
        parser.add_argument("--sample-limit", type=int, default=100, help="自动抽样设备上限")
        parser.add_argument("--batch-field", default="execute_time", help="strict 批次锚点字段，默认 execute_time")
        parser.add_argument(
            "--require-anchor-coverage",
            type=float,
            default=1.0,
            help="批次锚点覆盖率门槛（0~1），默认 1.0",
        )
        parser.add_argument(
            "--require-time-coverage",
            type=float,
            default=1.0,
            help="最小时间字段覆盖率门槛（0~1），默认 1.0",
        )
        parser.add_argument("--output", dest="output", help="将审计报告写入 JSON 文件")

    @staticmethod
    def _resolve_manage_ips(manage_ips, sample_limit=100):
        if manage_ips:
            return sorted(set(manage_ips))
        limit = max(1, int(sample_limit or 100))
        return list(
            NetworkDevice.objects.filter(status=0, auto_enable=True)
            .values_list("manage_ip", flat=True)[:limit]
        )

    @classmethod
    def _build_collection_report(cls, manage_ips, collection_name, batch_field):
        mongo = MongoOps(db="Automation", coll=collection_name).coll
        base_query = {"hostip": {"$in": manage_ips}}
        total_docs = mongo.count_documents(base_query)
        anchor_docs = mongo.count_documents(
            {
                **base_query,
                batch_field: {"$exists": True, "$ne": None},
            }
        )
        time_docs = mongo.count_documents(
            {
                **base_query,
                "$or": [{field: {"$exists": True, "$ne": None}} for field in cls.LEGACY_TIME_FIELDS],
            }
        )
        sample = mongo.find_one(
            base_query,
            {
                "_id": 0,
                "hostip": 1,
                batch_field: 1,
                **{field: 1 for field in cls.LEGACY_TIME_FIELDS},
            },
        )

        if total_docs > 0:
            anchor_coverage = round(anchor_docs / total_docs, 6)
            time_coverage = round(time_docs / total_docs, 6)
        else:
            anchor_coverage = 0.0
            time_coverage = 0.0

        return {
            "collection": collection_name,
            "total_docs": total_docs,
            "batch_field": batch_field,
            "anchor_docs": anchor_docs,
            "anchor_coverage": anchor_coverage,
            "time_docs": time_docs,
            "time_coverage": time_coverage,
            "sample_time_fields": sample or {},
        }

    def handle(self, *args, **options):
        manage_ips = self._resolve_manage_ips(
            manage_ips=options.get("manage_ips") or [],
            sample_limit=options.get("sample_limit") or 100,
        )
        batch_field = options.get("batch_field") or "execute_time"
        require_anchor_coverage = float(options.get("require_anchor_coverage") or 1.0)
        require_time_coverage = float(options.get("require_time_coverage") or 1.0)

        collections = [
            self._build_collection_report(
                manage_ips=manage_ips,
                collection_name=collection_name,
                batch_field=batch_field,
            )
            for collection_name in self.LEGACY_COLLECTIONS
        ]

        anchor_failed = [
            item["collection"] for item in collections if item["anchor_coverage"] < require_anchor_coverage
        ]
        time_failed = [
            item["collection"] for item in collections if item["time_coverage"] < require_time_coverage
        ]
        checks = {
            "sample_has_devices": bool(manage_ips),
            "anchor_coverage_gate_passed": not anchor_failed,
            "time_coverage_gate_passed": not time_failed,
        }
        status = "pass" if all(checks.values()) else "fail"

        report = {
            "generated_at": datetime.now().isoformat(),
            "batch_field": batch_field,
            "sample_manage_ips": manage_ips,
            "requirements": {
                "require_anchor_coverage": require_anchor_coverage,
                "require_time_coverage": require_time_coverage,
            },
            "collections": collections,
            "gate": {
                "status": status,
                "checks": checks,
                "anchor_failed_collections": anchor_failed,
                "time_failed_collections": time_failed,
            },
        }

        self.stdout.write(self.style.SUCCESS("legacy 时间锚点审计完成"))
        self.stdout.write(
            f"gate: status={status} sample_devices={len(manage_ips)} "
            f"anchor_failed={len(anchor_failed)} time_failed={len(time_failed)}"
        )
        if anchor_failed:
            self.stdout.write("anchor_failed_collections: " + ",".join(anchor_failed))
        if time_failed:
            self.stdout.write("time_failed_collections: " + ",".join(time_failed))

        output = options.get("output")
        if output:
            output_path = Path(output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            self.stdout.write(f"report written: {output_path}")
