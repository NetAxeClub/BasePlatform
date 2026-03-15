import math
import re
import time
from collections import OrderedDict, defaultdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from apps.asset.models import NetworkDevice
from django.utils import timezone

from apps.network_analysis.models import (
    AddressTraceSnapshot,
    AnalysisRun,
    InterfaceUtilizationSnapshot,
)
from utils.db.mongo_ops import MongoOps


INTERFACE_COLLECTION = MongoOps(db="Automation", coll="plan_interface_brief")
ARP_COLLECTION = MongoOps(db="Automation", coll="plan_arp")
MAC_COLLECTION = MongoOps(db="Automation", coll="plan_mac")
LLDP_COLLECTION = MongoOps(db="Automation", coll="plan_lldp")
AGGRE_COLLECTION = MongoOps(db="Automation", coll="plan_aggre_port")
IP_INTERFACE_COLLECTION = MongoOps(db="Automation", coll="plan_ip_interface")

SKIPPED_INTERFACE_PREFIXES = (
    "lo",
    "mgmt",
    "m-gigabitethernet",
    "aggregateport",
    "loopback",
    "vlan-interface",
    "route",
    "vsi",
    "meth",
    "virtual-if",
    "null",
    "smartgroup",
    "eth-trunk",
)


def _normalize_speed(speed_value: str) -> str:
    if not speed_value:
        return ""
    speed = str(speed_value).upper()
    if speed in {"1000M", "1000MBPS"}:
        return "1G"
    if speed in {"10000M", "10000MBPS"}:
        return "10G"
    return speed


def _interface_component_key(interface_name: str) -> Optional[int]:
    if not interface_name or "/" not in interface_name:
        return None
    part = interface_name.split("/")[0]
    if part and part[-1].isdigit():
        return int(part[-1])
    return None


def _skip_interface(interface_name: str) -> bool:
    lowered = (interface_name or "").lower()
    return any(lowered.startswith(prefix) for prefix in SKIPPED_INTERFACE_PREFIXES)


def _build_device_context() -> Dict[str, List[dict]]:
    result = defaultdict(list)
    queryset = NetworkDevice.objects.filter(status=0).values(
        "serial_num",
        "manage_ip",
        "name",
        "chassis",
        "slot",
        "idc__name",
        "idc_model__name",
        "rack__name",
        "u_location_start",
        "u_location_end",
        "category__name",
    )
    for row in queryset:
        result[row["manage_ip"]].append(row)
    return result


def _latest_batch_rows(
    collection: MongoOps,
    batch_fields: Tuple[str, ...],
    query: Optional[dict] = None,
) -> List[dict]:
    rows = collection.find(query_dict=query, fields={"_id": 0})
    latest_by_batch = {}
    for row in rows:
        batch_key = tuple(row.get(field) for field in batch_fields)
        execute_time = str(row.get("execute_time", "") or "")
        current = latest_by_batch.get(batch_key)
        if not current or execute_time >= str(current.get("execute_time", "") or ""):
            latest_by_batch[batch_key] = row

    latest_times = {
        batch_key: str(row.get("execute_time", "") or "")
        for batch_key, row in latest_by_batch.items()
    }
    filtered = []
    for row in rows:
        batch_key = tuple(row.get(field) for field in batch_fields)
        if str(row.get("execute_time", "") or "") == latest_times.get(batch_key, ""):
            filtered.append(row)
    return filtered


class InterfaceUtilizationAnalysisService:
    @staticmethod
    def _latest_interface_rows(device_ip: Optional[str] = None, execute_time: Optional[str] = None) -> List[dict]:
        query = {"hostip": device_ip} if device_ip else {}
        if execute_time:
            query["execute_time"] = execute_time
        rows = _latest_batch_rows(INTERFACE_COLLECTION, ("hostip",), query=query)
        latest_by_key = OrderedDict()
        for row in rows:
            latest_by_key[(row.get("hostip"), row.get("interface"))] = row
        return list(latest_by_key.values())

    @classmethod
    def build_snapshots(cls, device_ip: Optional[str] = None, execute_time: Optional[str] = None) -> List[dict]:
        rows = cls._latest_interface_rows(device_ip=device_ip, execute_time=execute_time)
        device_context = _build_device_context()
        grouped = defaultdict(list)

        for row in rows:
            interface_name = row.get("interface", "")
            if _skip_interface(interface_name):
                continue
            manage_ip = row.get("hostip")
            grouped[manage_ip].append(row)

        snapshots = []
        for manage_ip, interfaces in grouped.items():
            device_rows = device_context.get(manage_ip, [])
            slot_keys = sorted({item["slot"] for item in device_rows if item.get("slot")})
            chassis_keys = sorted({item["chassis"] for item in device_rows if item.get("chassis")})
            interface_keys = sorted(
                {key for key in (_interface_component_key(item.get("interface", "")) for item in interfaces) if key is not None}
            )

            if interface_keys and slot_keys and interface_keys == slot_keys:
                scope = InterfaceUtilizationSnapshot.SCOPE_SLOT
            elif interface_keys and chassis_keys and interface_keys == chassis_keys:
                scope = InterfaceUtilizationSnapshot.SCOPE_CHASSIS
            else:
                scope = InterfaceUtilizationSnapshot.SCOPE_DEVICE

            bucketed = defaultdict(list)
            for item in interfaces:
                key = _interface_component_key(item.get("interface", "")) if scope != InterfaceUtilizationSnapshot.SCOPE_DEVICE else 0
                bucketed[key].append(item)

            for key, bucket in bucketed.items():
                sample_device = None
                if scope == InterfaceUtilizationSnapshot.SCOPE_SLOT:
                    sample_device = next((row for row in device_rows if row.get("slot") == key), None)
                elif scope == InterfaceUtilizationSnapshot.SCOPE_CHASSIS:
                    sample_device = next((row for row in device_rows if row.get("chassis") == key), None)
                if sample_device is None and device_rows:
                    sample_device = device_rows[0]
                if sample_device is None:
                    continue

                used_speed_counts = defaultdict(int)
                unused_speed_counts = defaultdict(int)
                total_ports = 0
                used_ports = 0
                unused_ports = 0
                execute_time = ""

                for item in bucket:
                    status = str(item.get("status", "") or "").upper()
                    speed = _normalize_speed(item.get("speed", ""))
                    execute_time = max(execute_time, str(item.get("execute_time", "") or ""))
                    total_ports += 1
                    if status == "UP":
                        used_ports += 1
                        used_speed_counts[speed] += 1
                    else:
                        unused_ports += 1
                        unused_speed_counts[speed] += 1

                dominant_speed = ""
                combined = {**used_speed_counts}
                for speed, count in unused_speed_counts.items():
                    combined[speed] = combined.get(speed, 0) + count
                if combined:
                    dominant_speed = max(combined.items(), key=lambda item: item[1])[0]

                snapshots.append(
                    {
                        "device_serial_num": sample_device.get("serial_num", ""),
                        "manage_ip": manage_ip,
                        "device_name": sample_device.get("name", ""),
                        "component_scope": scope,
                        "component_key": str(key) if scope != InterfaceUtilizationSnapshot.SCOPE_DEVICE else "",
                        "component_name": f"{scope}-{key}" if scope != InterfaceUtilizationSnapshot.SCOPE_DEVICE else sample_device.get("name", ""),
                        "dominant_speed": dominant_speed,
                        "total_ports": total_ports,
                        "used_ports": used_ports,
                        "unused_ports": unused_ports,
                        "utilization_percent": round((used_ports / total_ports) * 100, 2) if total_ports else 0.0,
                        "used_speed_counts": dict(used_speed_counts),
                        "unused_speed_counts": dict(unused_speed_counts),
                        "source_execute_time": execute_time,
                    }
                )
        return snapshots

    @classmethod
    def refresh(cls, device_ip: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, int]:
        snapshots = cls.build_snapshots(device_ip=device_ip, execute_time=execute_time)
        touched = 0
        for snapshot in snapshots:
            InterfaceUtilizationSnapshot.objects.update_or_create(
                device_serial_num=snapshot["device_serial_num"],
                component_scope=snapshot["component_scope"],
                component_key=snapshot["component_key"],
                defaults=snapshot,
            )
            touched += 1
        return {"snapshots": touched, "execute_time": execute_time or ""}

    @staticmethod
    def overview(device_ip: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, object]:
        queryset = InterfaceUtilizationSnapshot.objects.all()
        if device_ip:
            queryset = queryset.filter(manage_ip=device_ip)
        if execute_time:
            queryset = queryset.filter(source_execute_time=execute_time)
        snapshots = list(queryset)
        if not snapshots:
            return {
                "snapshots": 0,
                "devices": 0,
                "avg_utilization": 0.0,
                "high_utilization": 0,
                "latest_batches": [],
                "by_scope": {},
            }
        by_scope = defaultdict(int)
        high_utilization = 0
        batches = set()
        device_ids = set()
        total_utilization = 0.0
        for item in snapshots:
            by_scope[item.component_scope] += 1
            if item.utilization_percent >= 80:
                high_utilization += 1
            if item.source_execute_time:
                batches.add(item.source_execute_time)
            if item.device_serial_num:
                device_ids.add(item.device_serial_num)
            total_utilization += item.utilization_percent or 0
        return {
            "snapshots": len(snapshots),
            "devices": len(device_ids),
            "avg_utilization": round(total_utilization / len(snapshots), 2),
            "high_utilization": high_utilization,
            "latest_batches": sorted(batches, reverse=True)[:5],
            "by_scope": dict(by_scope),
        }

    @staticmethod
    def quality_summary(device_ip: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, object]:
        queryset = InterfaceUtilizationSnapshot.objects.all()
        if device_ip:
            queryset = queryset.filter(manage_ip=device_ip)
        if execute_time:
            queryset = queryset.filter(source_execute_time=execute_time)
        snapshots = list(queryset)
        zero_total = 0
        missing_speed = 0
        stale_batch = 0
        for item in snapshots:
            if item.total_ports == 0:
                zero_total += 1
            if not item.dominant_speed:
                missing_speed += 1
            if not item.source_execute_time:
                stale_batch += 1
        return {
            "snapshots": len(snapshots),
            "zero_total_ports": zero_total,
            "missing_dominant_speed": missing_speed,
            "missing_batch_marker": stale_batch,
        }


class AddressTrackingAnalysisService:
    @staticmethod
    def _latest_rows(collection: MongoOps, key_fields: Tuple[str, ...], execute_time: Optional[str] = None) -> List[dict]:
        query = {"execute_time": execute_time} if execute_time else None
        rows = collection.find(query_dict=query, fields={"_id": 0})
        latest = {}
        for row in rows:
            key = tuple(row.get(field) for field in key_fields)
            execute_time = str(row.get("execute_time", "") or "")
            current = latest.get(key)
            if not current or execute_time >= str(current.get("execute_time", "") or ""):
                latest[key] = row
        return list(latest.values())

    @staticmethod
    def _build_location(row: dict) -> str:
        idc_model = row.get("idc_model__name") or ""
        rack = row.get("rack__name") or ""
        start = row.get("u_location_start")
        end = row.get("u_location_end")
        if any(item for item in (idc_model, rack, start, end)):
            return f"{idc_model}_{rack}_{start}-{end}"
        return ""

    @classmethod
    def build_traces(cls, ip_address: Optional[str] = None, execute_time: Optional[str] = None) -> List[dict]:
        device_context = _build_device_context()
        arp_rows = cls._latest_rows(ARP_COLLECTION, ("hostip", "ipaddress", "macaddress", "interface"), execute_time=execute_time)
        mac_rows = cls._latest_rows(MAC_COLLECTION, ("hostip", "macaddress", "interface"), execute_time=execute_time)
        lldp_rows = cls._latest_rows(LLDP_COLLECTION, ("hostip", "local_interface", "neighbor_ip", "neighbor_port"), execute_time=execute_time)
        aggre_rows = cls._latest_rows(AGGRE_COLLECTION, ("hostip", "aggregroup"), execute_time=execute_time)
        ip_rows = cls._latest_rows(IP_INTERFACE_COLLECTION, ("hostip", "ipaddress", "interface"), execute_time=execute_time)

        mac_index = defaultdict(list)
        for row in mac_rows:
            mac_index[(row.get("macaddress"), row.get("idc_name"))].append(row)

        lldp_index = defaultdict(list)
        lldp_reverse_index = defaultdict(list)
        for row in lldp_rows:
            lldp_index[(row.get("hostip"), row.get("local_interface"))].append(row)
            lldp_reverse_index[(row.get("hostip"), row.get("neighbor_port"))].append(row)

        aggre_index = {
            (row.get("hostip"), row.get("aggregroup")): row for row in aggre_rows
        }
        ip_interface_index = defaultdict(list)
        for row in ip_rows:
            ip_interface_index[(row.get("hostip"), row.get("ipaddress"))].append(row)

        target_arp_rows = [row for row in arp_rows if not ip_address or row.get("ipaddress") == ip_address]
        traces = []
        for arp in target_arp_rows:
            mac_candidates = mac_index.get((arp.get("macaddress"), arp.get("idc_name")), [])
            if not mac_candidates:
                mac_candidates = [arp]

            candidates = []
            for mac_row in mac_candidates:
                manage_ip = mac_row.get("hostip")
                interface_name = mac_row.get("interface") or arp.get("interface") or ""
                member_ports = []
                trace_method = "arp-mac"
                trace_status = AddressTraceSnapshot.STATUS_PARTIAL
                trace_details = {"arp_host": arp.get("hostip"), "mac_host": manage_ip}

                aggre = aggre_index.get((manage_ip, interface_name))
                if aggre:
                    member_ports = aggre.get("memberports") or []
                    interface_candidates = member_ports
                    trace_method = "aggregation"
                else:
                    interface_candidates = [interface_name]

                resolved = False
                for port in interface_candidates:
                    lldp_candidates = lldp_index.get((manage_ip, port), []) + lldp_reverse_index.get((manage_ip, port), [])
                    for lldp in lldp_candidates:
                        neighbor_ip = lldp.get("neighbor_ip")
                        if neighbor_ip and ip_interface_index.get((neighbor_ip, arp.get("ipaddress"))):
                            trace_status = AddressTraceSnapshot.STATUS_LOCATED
                            trace_method = "lldp-neighbor"
                            trace_details["neighbor_ip"] = neighbor_ip
                            resolved = True
                            break
                    if resolved:
                        break

                device_rows = device_context.get(manage_ip, [])
                sample_device = device_rows[0] if device_rows else {}
                candidates.append(
                    {
                        "ip_address": arp.get("ipaddress"),
                        "mac_address": arp.get("macaddress") or "",
                        "device_serial_num": sample_device.get("serial_num", ""),
                        "manage_ip": manage_ip,
                        "device_name": sample_device.get("name", ""),
                        "idc_name": sample_device.get("idc__name", "") or arp.get("idc_name", ""),
                        "category_name": sample_device.get("category__name", ""),
                        "node_location": cls._build_location(sample_device),
                        "interface_name": interface_name,
                        "member_ports": member_ports,
                        "trace_status": trace_status,
                        "trace_method": trace_method,
                        "trace_details": trace_details,
                        "source_execute_time": str(arp.get("execute_time", "") or ""),
                    }
                )

            deduped = OrderedDict()
            for candidate in candidates:
                deduped.setdefault((candidate["ip_address"], candidate["manage_ip"]), candidate)
            traces.extend(deduped.values())
        return traces

    @classmethod
    def refresh(cls, ip_address: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, int]:
        traces = cls.build_traces(ip_address=ip_address, execute_time=execute_time)
        touched = 0
        for trace in traces:
            AddressTraceSnapshot.objects.update_or_create(
                ip_address=trace["ip_address"],
                manage_ip=trace["manage_ip"],
                interface_name=trace["interface_name"],
                defaults=trace,
            )
            touched += 1
        return {"traces": touched, "execute_time": execute_time or ""}

    @staticmethod
    def overview(ip_address: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, object]:
        queryset = AddressTraceSnapshot.objects.all()
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        if execute_time:
            queryset = queryset.filter(source_execute_time=execute_time)
        traces = list(queryset)
        status_counter = defaultdict(int)
        method_counter = defaultdict(int)
        batches = set()
        unique_ips = set()
        for item in traces:
            status_counter[item.trace_status] += 1
            if item.trace_method:
                method_counter[item.trace_method] += 1
            if item.source_execute_time:
                batches.add(item.source_execute_time)
            unique_ips.add(item.ip_address)
        located = status_counter.get(AddressTraceSnapshot.STATUS_LOCATED, 0)
        partial = status_counter.get(AddressTraceSnapshot.STATUS_PARTIAL, 0)
        total = len(traces)
        return {
            "traces": total,
            "unique_ips": len(unique_ips),
            "located": located,
            "partial": partial,
            "unresolved": status_counter.get(AddressTraceSnapshot.STATUS_UNRESOLVED, 0),
            "located_rate": round((located / total) * 100, 2) if total else 0.0,
            "coverage_rate": round(((located + partial) / total) * 100, 2) if total else 0.0,
            "latest_batches": sorted(batches, reverse=True)[:5],
            "by_method": dict(method_counter),
        }

    @staticmethod
    def quality_summary(ip_address: Optional[str] = None, execute_time: Optional[str] = None) -> Dict[str, object]:
        queryset = AddressTraceSnapshot.objects.all()
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)
        if execute_time:
            queryset = queryset.filter(source_execute_time=execute_time)
        traces = list(queryset)
        missing_mac = 0
        missing_location = 0
        missing_batch = 0
        aggregation_paths = 0
        for item in traces:
            if not item.mac_address:
                missing_mac += 1
            if not item.node_location:
                missing_location += 1
            if not item.source_execute_time:
                missing_batch += 1
            if item.member_ports:
                aggregation_paths += 1
        return {
            "traces": len(traces),
            "missing_mac": missing_mac,
            "missing_location": missing_location,
            "missing_batch_marker": missing_batch,
            "aggregation_paths": aggregation_paths,
        }


class NetworkAnalysisOrchestratorService:
    @staticmethod
    def _start_run(run_kind: str, manage_ip: Optional[str], ip_address: Optional[str], triggered_by: str) -> AnalysisRun:
        return AnalysisRun.objects.create(
            run_kind=run_kind,
            target_manage_ip=manage_ip,
            target_ip_address=ip_address,
            triggered_by=triggered_by,
            status=AnalysisRun.STATUS_RUNNING,
            started_at=timezone.now(),
        )

    @staticmethod
    def _finish_run(run: AnalysisRun, summary: dict, error_message: str = "") -> AnalysisRun:
        run.summary = summary
        run.error_message = error_message
        run.status = AnalysisRun.STATUS_FAILED if error_message else AnalysisRun.STATUS_SUCCESS
        run.finished_at = timezone.now()
        run.save(update_fields=["summary", "error_message", "status", "finished_at", "updated_at"])
        return run

    @classmethod
    def refresh_interface_utilization(
        cls,
        manage_ip: Optional[str] = None,
        triggered_by: str = "system",
        execute_time: Optional[str] = None,
    ) -> dict:
        run = cls._start_run(AnalysisRun.KIND_INTERFACE_UTILIZATION, manage_ip, None, triggered_by)
        try:
            refresh_result = InterfaceUtilizationAnalysisService.refresh(device_ip=manage_ip, execute_time=execute_time)
            summary = {
                "refresh": refresh_result,
                "overview": InterfaceUtilizationAnalysisService.overview(device_ip=manage_ip, execute_time=execute_time),
                "quality": InterfaceUtilizationAnalysisService.quality_summary(device_ip=manage_ip, execute_time=execute_time),
                "execute_time": execute_time or "",
            }
            cls._finish_run(run, summary)
            return {"run_id": run.id, **summary}
        except Exception as exc:
            cls._finish_run(run, {}, str(exc))
            raise

    @classmethod
    def refresh_address_tracking(
        cls,
        ip_address: Optional[str] = None,
        triggered_by: str = "system",
        execute_time: Optional[str] = None,
    ) -> dict:
        run = cls._start_run(AnalysisRun.KIND_ADDRESS_TRACKING, None, ip_address, triggered_by)
        try:
            refresh_result = AddressTrackingAnalysisService.refresh(ip_address=ip_address, execute_time=execute_time)
            summary = {
                "refresh": refresh_result,
                "overview": AddressTrackingAnalysisService.overview(ip_address=ip_address, execute_time=execute_time),
                "quality": AddressTrackingAnalysisService.quality_summary(ip_address=ip_address, execute_time=execute_time),
                "execute_time": execute_time or "",
            }
            cls._finish_run(run, summary)
            return {"run_id": run.id, **summary}
        except Exception as exc:
            cls._finish_run(run, {}, str(exc))
            raise

    @classmethod
    def refresh_all(
        cls,
        manage_ip: Optional[str] = None,
        ip_address: Optional[str] = None,
        triggered_by: str = "system",
        execute_time: Optional[str] = None,
    ) -> dict:
        run = cls._start_run(AnalysisRun.KIND_FULL_REFRESH, manage_ip, ip_address, triggered_by)
        try:
            interface_summary = {
                "refresh": InterfaceUtilizationAnalysisService.refresh(device_ip=manage_ip, execute_time=execute_time),
                "overview": InterfaceUtilizationAnalysisService.overview(device_ip=manage_ip, execute_time=execute_time),
                "quality": InterfaceUtilizationAnalysisService.quality_summary(device_ip=manage_ip, execute_time=execute_time),
                "execute_time": execute_time or "",
            }
            trace_summary = {
                "refresh": AddressTrackingAnalysisService.refresh(ip_address=ip_address, execute_time=execute_time),
                "overview": AddressTrackingAnalysisService.overview(ip_address=ip_address, execute_time=execute_time),
                "quality": AddressTrackingAnalysisService.quality_summary(ip_address=ip_address, execute_time=execute_time),
                "execute_time": execute_time or "",
            }
            summary = {
                "interface_utilization": interface_summary,
                "address_tracking": trace_summary,
            }
            cls._finish_run(run, summary)
            return {"run_id": run.id, **summary}
        except Exception as exc:
            cls._finish_run(run, {}, str(exc))
            raise

    @classmethod
    def wait_and_refresh_batch(
        cls,
        execute_time: str,
        expected_devices: int = 0,
        expected_subtasks: int = 0,
        wait_seconds: int = 15,
        max_attempts: int = 20,
        triggered_by: str = "device_api-batch",
    ) -> dict:
        from apps.device_api import COLLECTION_PLAN, COLLECTION_SUB_PLAN

        attempts = 0
        while attempts < max_attempts:
            parent_count = COLLECTION_PLAN.count_documents({"execute_time": execute_time})
            subtask_count = COLLECTION_SUB_PLAN.count_documents({"execute_time": execute_time})
            if (expected_devices == 0 or parent_count >= expected_devices) and (
                expected_subtasks == 0 or subtask_count >= expected_subtasks
            ):
                break
            time.sleep(wait_seconds)
            attempts += 1

        result = cls.refresh_all(
            triggered_by=triggered_by,
            execute_time=execute_time,
        )
        result["monitor"] = {
            "attempts": attempts,
            "expected_devices": expected_devices,
            "expected_subtasks": expected_subtasks,
            "parent_count": COLLECTION_PLAN.count_documents({"execute_time": execute_time}),
            "subtask_count": COLLECTION_SUB_PLAN.count_documents({"execute_time": execute_time}),
        }
        return result
