import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.asset.models import NetworkDevice
from utils.db.mongo_ops import MongoOps


class Command(BaseCommand):
    help = "为 legacy 结果集合回填 execute_time 批次锚点；默认 dry-run，需显式 --apply 才会写库。"

    LEGACY_COLLECTIONS = [
        "ARPTable",
        "MACTable",
        "LLDPTable",
        "layer2interface",
        "layer3interface",
        "AggreTable",
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
        parser.add_argument(
            "--collection",
            dest="collections",
            action="append",
            default=[],
            help="仅处理指定集合，可重复传入；为空时处理默认六集合",
        )
        parser.add_argument("--execute-time", required=True, help="要回填的批次 execute_time 值")
        parser.add_argument("--batch-field", default="execute_time", help="批次锚点字段名，默认 execute_time")
        parser.add_argument("--max-update-docs", type=int, default=20000, help="单次回填最大文档数保护阈值")
        parser.add_argument("--force", action="store_true", help="超过保护阈值时仍允许执行")
        parser.add_argument("--apply", action="store_true", help="执行真实写库；未传入时仅 dry-run")
        parser.add_argument("--output", dest="output", help="将回填报告写入 JSON 文件")

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
    def _resolve_collections(cls, raw_collections):
        if not raw_collections:
            return list(cls.LEGACY_COLLECTIONS)
        valid = set(cls.LEGACY_COLLECTIONS)
        unknown = sorted(set(raw_collections) - valid)
        if unknown:
            raise CommandError(f"unsupported collections: {','.join(unknown)}")
        return sorted(set(raw_collections))

    @staticmethod
    def _anchor_missing_query(base_query, batch_field):
        return {
            **base_query,
            "$or": [
                {batch_field: {"$exists": False}},
                {batch_field: None},
                {batch_field: ""},
            ],
        }

    def handle(self, *args, **options):
        execute_time = (options.get("execute_time") or "").strip()
        if not execute_time:
            raise CommandError("execute_time is required")

        manage_ips = self._resolve_manage_ips(
            manage_ips=options.get("manage_ips") or [],
            sample_limit=options.get("sample_limit") or 100,
        )
        if not manage_ips:
            raise CommandError("no manage_ips resolved")

        collections = self._resolve_collections(options.get("collections") or [])
        batch_field = options.get("batch_field") or "execute_time"
        max_update_docs = max(1, int(options.get("max_update_docs") or 20000))
        apply_mode = bool(options.get("apply"))
        force = bool(options.get("force"))

        reports = []
        total_to_update = 0
        total_updated = 0

        for collection_name in collections:
            mongo = MongoOps(db="Automation", coll=collection_name).coll
            base_query = {"hostip": {"$in": manage_ips}}
            missing_query = self._anchor_missing_query(base_query=base_query, batch_field=batch_field)

            total_docs = mongo.count_documents(base_query)
            missing_docs = mongo.count_documents(missing_query)
            existing_docs = max(0, total_docs - missing_docs)

            updated_docs = 0
            if apply_mode and missing_docs:
                if missing_docs > max_update_docs and not force:
                    raise CommandError(
                        f"collection={collection_name} missing_docs={missing_docs} "
                        f"exceeds max_update_docs={max_update_docs}; use --force to continue"
                    )
                update_res = mongo.update_many(
                    missing_query,
                    {
                        "$set": {
                            batch_field: execute_time,
                            "legacy_anchor_backfilled": True,
                            "legacy_anchor_backfilled_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    },
                )
                updated_docs = getattr(update_res, "modified_count", 0) or 0

            total_to_update += missing_docs
            total_updated += updated_docs
            reports.append(
                {
                    "collection": collection_name,
                    "total_docs": total_docs,
                    "anchor_existing_docs": existing_docs,
                    "anchor_missing_docs": missing_docs,
                    "updated_docs": updated_docs,
                    "anchor_coverage_after_estimated": (
                        round((existing_docs + (updated_docs if apply_mode else missing_docs)) / total_docs, 6)
                        if total_docs
                        else 0.0
                    ),
                }
            )

        summary = {
            "apply_mode": apply_mode,
            "collections": len(reports),
            "total_to_update": total_to_update,
            "total_updated": total_updated,
            "all_collections_coverable": all(item["anchor_missing_docs"] >= 0 for item in reports),
        }

        report = {
            "generated_at": datetime.now().isoformat(),
            "execute_time": execute_time,
            "batch_field": batch_field,
            "manage_ips": manage_ips,
            "summary": summary,
            "collections": reports,
        }

        self.stdout.write(self.style.SUCCESS("legacy execute_time 回填检查完成"))
        self.stdout.write(
            f"apply_mode={apply_mode} collections={len(reports)} "
            f"to_update={total_to_update} updated={total_updated}"
        )
        for item in reports:
            self.stdout.write(
                f"collection={item['collection']} total={item['total_docs']} "
                f"missing={item['anchor_missing_docs']} updated={item['updated_docs']}"
            )

        output = options.get("output")
        if output:
            output_path = Path(output).expanduser()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.stdout.write(f"report written: {output_path}")

        if apply_mode:
            self.stdout.write("post_check: run audit_legacy_time_anchor to verify anchor coverage gate")
        else:
            self.stdout.write("dry_run: use --apply to execute backfill")
