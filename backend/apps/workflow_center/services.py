import json

import requests

from apps.asset.models import Category, NetworkDevice
from apps.asset.serializers import NetworkDeviceSerializer
from apps.network_analysis.models import AddressTraceSnapshot
from apps.network_analysis.serializers import AddressTraceSnapshotSerializer
from confload.confload import config
from driver import discovered_plugins
from utils.db.mongo_ops import MongoOps

plan_lldp_mongo = MongoOps(db="Automation", coll="plan_lldp")
plan_interface_mongo = MongoOps(db="Automation", coll="plan_interface_brief")
plan_ip_interface_mongo = MongoOps(db="Automation", coll="plan_ip_interface")


def get_firewall_list(manage_ip_list=None):
    category = Category.objects.filter(name="防火墙").values("id").first()
    if not category:
        return []

    queryset = NetworkDevice.objects.filter(
        auto_enable=True,
        status=0,
        category=category["id"],
        ha_status__in=[0, 1],
    )
    if manage_ip_list:
        queryset = queryset.filter(manage_ip__in=manage_ip_list)

    return list(
        queryset.select_related("vendor", "category")
        .prefetch_related("bind_ip")
        .values("id", "manage_ip", "name", "vendor__alias", "bind_ip__ipaddr", "soft_version")
    )


class WorkflowDiagnoseService:
    def __init__(self, ip_address):
        self.ip_address = ip_address

    def get_address_traces(self):
        traces = AddressTraceSnapshot.objects.filter(ip_address=self.ip_address).order_by("-observed_at")
        return AddressTraceSnapshotSerializer(traces, many=True).data

    def get_cmdb(self, manage_ip):
        res = []
        devices = NetworkDevice.objects.filter(manage_ip=manage_ip).values()
        if devices:
            for device in devices:
                instance = NetworkDevice.objects.get(pk=device["id"])
                serializer = NetworkDeviceSerializer(instance)
                res.append(serializer.data)
        return res

    def get_log(self, manage_ip, name):
        res = []
        plugin = discovered_plugins.get("plugins.extensibles.elasticsearch")
        if plugin is not None:
            methods = sorted([x for x in plugin.__all__])
            for method in methods:
                target = getattr(plugin, method, None)
                if callable(target):
                    res += target(**dict(hostip=manage_ip, severity="", time_range="", hostname=name))
        return res

    def get_lldp(self, manage_ip):
        rows = plan_lldp_mongo.find(query_dict=dict(hostip=manage_ip), fields={"_id": 0})
        latest = {}
        for row in rows:
            key = (row.get("hostip"), row.get("local_interface"), row.get("neighbor_ip"))
            execute_time = str(row.get("execute_time", "") or "")
            current = latest.get(key)
            if not current or execute_time >= str(current.get("execute_time", "") or ""):
                latest[key] = row
        return list(latest.values())

    def get_alert(self, manage_ip):
        alert_server = config.service_dicovery("alert_gateway")
        server_hosts = alert_server["hosts"]
        if server_hosts:
            url = "http://{}:{}/alert_gateway/problem/problem/".format(
                server_hosts[0]["ip"], server_hosts[0]["port"]
            )
            payload = {
                "query": json.dumps({"hostip": manage_ip}),
                "page": 1,
                "page_size": 1000,
            }
            headers = {
                "Content-Type": "application/json",
                "x-api-key": config.alert_gateway_api,
            }

            res = requests.request("GET", url, headers=headers, params=payload)
            if res.status_code == 200:
                return res.json()["data"]
        return []


def get_device_interfaces(manage_ip):
    layer3interface_res = plan_ip_interface_mongo.find(query_dict={"hostip": manage_ip}, fields={"interface": 1, "_id": 0})
    layer2interface_res = plan_interface_mongo.find(query_dict={"hostip": manage_ip}, fields={"interface": 1, "_id": 0})
    interfaces = []
    seen = set()
    for row in layer3interface_res + layer2interface_res:
        interface_name = row.get("interface")
        if interface_name and interface_name not in seen:
            seen.add(interface_name)
            interfaces.append(interface_name)
    return interfaces


TRACE_FILTER_ALIAS_MAP = {
    "server_ip_address": "ip_address",
    "server_mac_address": "mac_address",
    "node_ip": "manage_ip",
    "node_hostname": "device_name",
    "node_interface": "interface_name",
    "serial_num": "device_serial_num",
    "category_name": "category_name",
    "idc_name": "idc_name",
    "trace_status": "trace_status",
    "trace_method": "trace_method",
    "execute_time": "source_execute_time",
    "source_execute_time": "source_execute_time",
}


def get_address_trace_columns():
    return [
        {"title": "设备名称", "key": "device_name"},
        {"title": "机房", "key": "idc_name"},
        {"title": "设备序列号", "key": "device_serial_num"},
        {"title": "管理IP", "key": "manage_ip"},
        {"title": "接入口", "key": "interface_name"},
        {"title": "接入位置", "key": "node_location"},
        {"title": "目标IP", "key": "ip_address"},
        {"title": "MAC地址", "key": "mac_address"},
        {"title": "定位状态", "key": "trace_status"},
        {"title": "定位方式", "key": "trace_method"},
        {"title": "观测时间", "key": "observed_at"},
    ]


def query_address_traces(params, last=False, page_size=10, page_num=1):
    filters = {}
    for key, value in params.items():
        if not value:
            continue
        mapped_key = TRACE_FILTER_ALIAS_MAP.get(key, key)
        if mapped_key in {
            "ip_address",
            "mac_address",
            "manage_ip",
            "device_name",
            "interface_name",
            "device_serial_num",
            "category_name",
            "idc_name",
            "trace_status",
            "trace_method",
            "source_execute_time",
        }:
            filters[mapped_key] = value

    queryset = AddressTraceSnapshot.objects.filter(**filters).order_by("-observed_at")
    if last:
        latest_execute_time = (
            AddressTraceSnapshot.objects.filter(**filters)
            .exclude(source_execute_time="")
            .order_by("-source_execute_time", "-observed_at")
            .values_list("source_execute_time", flat=True)
            .first()
        )
        if latest_execute_time:
            queryset = queryset.filter(source_execute_time=latest_execute_time)
        else:
            latest_time = queryset.values_list("observed_at", flat=True).first()
            if latest_time:
                queryset = queryset.filter(observed_at=latest_time)
            else:
                queryset = queryset.none()

    start = (page_num - 1) * page_size
    end = start + page_size
    serializer = AddressTraceSnapshotSerializer(queryset[start:end], many=True)
    return serializer.data, queryset.count()
