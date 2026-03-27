import logging
import os
import sys

import pymongo

from apps.device_api.contract import build_plan_collection_name
from apps.device_api import (
    COLLECTION_BINDING_ANALYSIS,
    COLLECTION_EXECUTION_LOG,
    COLLECTION_PLAN,
    COLLECTION_RESULTS_DB,
    COLLECTION_SUB_PLAN,
    aggre_port_mongo,
    arp_mongo,
    bgp_neighbors_mongo,
    bgp_summary_mongo,
    board_status_mongo,
    clock_status_mongo,
    cpu_status_mongo,
    device_identity_mongo,
    environment_status_mongo,
    fan_status_mongo,
    irf_status_mongo,
    interface_brief_mongo,
    ip_interface_mongo,
    isis_neighbors_mongo,
    lldp_mongo,
    hrp_state_mongo,
    address_set_mongo,
    nat_address_mongo,
    service_set_mongo,
    slb_info_mongo,
    vrrp_info_mongo,
    mac_mongo,
    mac_evpn_mongo,
    mac_bd_mongo,
    mac_vxlan_mongo,
    mac_vxlan_control_mongo,
    vxlan_capability_mongo,
    netconf_capability_mongo,
    cli_output_capability_mongo,
    zone_mongo,
    service_predefined_mongo,
    policy_hit_count_mongo,
    security_policy_mongo,
    dnat_mongo,
    snat_mongo,
    memory_status_mongo,
    ospf_interfaces_mongo,
    ospf_neighbors_mongo,
    power_status_mongo,
    route_table_mongo,
    stack_status_mongo,
    storage_status_mongo,
    temperature_status_mongo,
    transceiver_status_mongo,
)

logger = logging.getLogger(__name__)


MANAGEMENT_COMMANDS_SKIP_AUTO_INDEX = {
    "makemigrations",
    "migrate",
    "collectstatic",
    "shell",
    "dbshell",
    "showmigrations",
    "test",
}

PLAN_DATA_COLLECTIONS = {
    build_plan_collection_name("device_identity"): device_identity_mongo,
    build_plan_collection_name("arp"): arp_mongo,
    build_plan_collection_name("mac"): mac_mongo,
    build_plan_collection_name("mac_evpn"): mac_evpn_mongo,
    build_plan_collection_name("mac_bd"): mac_bd_mongo,
    build_plan_collection_name("mac_vxlan"): mac_vxlan_mongo,
    build_plan_collection_name("mac_vxlan_control"): mac_vxlan_control_mongo,
    build_plan_collection_name("vxlan_capability"): vxlan_capability_mongo,
    build_plan_collection_name("netconf_capability"): netconf_capability_mongo,
    build_plan_collection_name("cli_output_capability"): cli_output_capability_mongo,
    build_plan_collection_name("lldp"): lldp_mongo,
    build_plan_collection_name("ip_interface"): ip_interface_mongo,
    build_plan_collection_name("interface_brief"): interface_brief_mongo,
    build_plan_collection_name("aggre_port"): aggre_port_mongo,
    build_plan_collection_name("hrp_state"): hrp_state_mongo,
    build_plan_collection_name("address_set"): address_set_mongo,
    build_plan_collection_name("nat_address"): nat_address_mongo,
    build_plan_collection_name("service_set"): service_set_mongo,
    build_plan_collection_name("slb_info"): slb_info_mongo,
    build_plan_collection_name("vrrp_info"): vrrp_info_mongo,
    build_plan_collection_name("zone"): zone_mongo,
    build_plan_collection_name("service_predefined"): service_predefined_mongo,
    build_plan_collection_name("policy_hit_count"): policy_hit_count_mongo,
    build_plan_collection_name("security_policy"): security_policy_mongo,
    build_plan_collection_name("dnat"): dnat_mongo,
    build_plan_collection_name("snat"): snat_mongo,
    build_plan_collection_name("fan_status"): fan_status_mongo,
    build_plan_collection_name("power_status"): power_status_mongo,
    build_plan_collection_name("temperature_status"): temperature_status_mongo,
    build_plan_collection_name("cpu_status"): cpu_status_mongo,
    build_plan_collection_name("memory_status"): memory_status_mongo,
    build_plan_collection_name("board_status"): board_status_mongo,
    build_plan_collection_name("irf_status"): irf_status_mongo,
    build_plan_collection_name("stack_status"): stack_status_mongo,
    build_plan_collection_name("transceiver_status"): transceiver_status_mongo,
    build_plan_collection_name("storage_status"): storage_status_mongo,
    build_plan_collection_name("environment_status"): environment_status_mongo,
    build_plan_collection_name("clock_status"): clock_status_mongo,
    build_plan_collection_name("route_table"): route_table_mongo,
    build_plan_collection_name("bgp_neighbors"): bgp_neighbors_mongo,
    build_plan_collection_name("bgp_summary"): bgp_summary_mongo,
    build_plan_collection_name("ospf_neighbors"): ospf_neighbors_mongo,
    build_plan_collection_name("ospf_interfaces"): ospf_interfaces_mongo,
    build_plan_collection_name("isis_neighbors"): isis_neighbors_mongo,
}

PLAN_DATA_INDEXES = (
    (
        [("hostip", pymongo.ASCENDING), ("collection_type", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
        {"name": "idx_hostip_type_execute_time"},
    ),
    (
        [("summary_plan_id", pymongo.ASCENDING), ("plan_id", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
        {"name": "idx_summary_plan_plan_execute_time"},
    ),
    (
        [("plan_id", pymongo.ASCENDING), ("collection_method", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
        {"name": "idx_plan_method_execute_time"},
    ),
)

RESULT_COLLECTION_INDEXES = {
    "TestDeviceCollection": (
        (
            [("plan_id", pymongo.ASCENDING), ("collected_at", pymongo.DESCENDING)],
            {"name": "idx_plan_collected_at"},
        ),
        (
            [("device_ip", pymongo.ASCENDING), ("collection_method", pymongo.ASCENDING), ("collected_at", pymongo.DESCENDING)],
            {"name": "idx_device_method_collected_at"},
        ),
        (
            [("status", pymongo.ASCENDING), ("collected_at", pymongo.DESCENDING)],
            {"name": "idx_status_collected_at"},
        ),
    ),
    "PlanCollectionCelery": (
        (
            [("summary_plan_id", pymongo.ASCENDING), ("device_ip", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_summary_plan_device_execute_time"},
        ),
        (
            [("task_status", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_task_status_execute_time"},
        ),
    ),
    "SubPlanCollectionCelery": (
        (
            [("summary_plan_id", pymongo.ASCENDING), ("device_ip", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_summary_plan_device_execute_time"},
        ),
        (
            [("summary_plan_id", pymongo.ASCENDING), ("plan_id", pymongo.ASCENDING), ("collection_type", pymongo.ASCENDING), ("device_ip", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_summary_plan_plan_type_device_execute_time"},
        ),
        (
            [("task_status", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_task_status_execute_time"},
        ),
    ),
    "DeviceApiExecutionLog": (
        (
            [("execute_time", pymongo.DESCENDING), ("event_scope", pymongo.ASCENDING), ("severity", pymongo.ASCENDING)],
            {"name": "idx_execute_scope_severity"},
        ),
        (
            [("device_ip", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING), ("event_type", pymongo.ASCENDING)],
            {"name": "idx_device_execute_event"},
        ),
        (
            [("summary_plan_id", pymongo.ASCENDING), ("plan_id", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_summary_plan_execute_time"},
        ),
        (
            [("status", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_status_execute_time"},
        ),
    ),
    "DevicePlanBindingAnalysisChecklist": (
        (
            [("doc_type", pymongo.ASCENDING), ("execute_time", pymongo.DESCENDING)],
            {"name": "idx_doc_type_execute_time"},
        ),
        (
            [("execute_time", pymongo.DESCENDING), ("device_ip", pymongo.ASCENDING)],
            {"name": "idx_execute_time_device_ip"},
        ),
        (
            [("execute_time", pymongo.DESCENDING), ("has_recommendations", pymongo.ASCENDING)],
            {"name": "idx_execute_time_has_recommendations"},
        ),
    ),
}

_AUTO_INDEXES_BOOTSTRAPPED = False


def should_auto_ensure_device_api_indexes(argv=None) -> bool:
    if os.environ.get("DEVICE_API_SKIP_AUTO_INDEXES") == "1":
        return False

    argv = argv or sys.argv
    if len(argv) < 2:
        return True

    return argv[1] not in MANAGEMENT_COMMANDS_SKIP_AUTO_INDEX


def build_device_api_index_targets():
    targets = [
        ("TestDeviceCollection", COLLECTION_RESULTS_DB, RESULT_COLLECTION_INDEXES["TestDeviceCollection"]),
        ("PlanCollectionCelery", COLLECTION_PLAN, RESULT_COLLECTION_INDEXES["PlanCollectionCelery"]),
        ("SubPlanCollectionCelery", COLLECTION_SUB_PLAN, RESULT_COLLECTION_INDEXES["SubPlanCollectionCelery"]),
        ("DeviceApiExecutionLog", COLLECTION_EXECUTION_LOG, RESULT_COLLECTION_INDEXES["DeviceApiExecutionLog"]),
        (
            "DevicePlanBindingAnalysisChecklist",
            COLLECTION_BINDING_ANALYSIS,
            RESULT_COLLECTION_INDEXES["DevicePlanBindingAnalysisChecklist"],
        ),
    ]
    for collection_name, mongo in PLAN_DATA_COLLECTIONS.items():
        targets.append((collection_name, mongo, PLAN_DATA_INDEXES))
    return targets


def ensure_device_api_mongo_indexes():
    created_indexes = []
    for collection_name, mongo, index_specs in build_device_api_index_targets():
        for keys, options in index_specs:
            index_name = mongo.create_index(keys, **options)
            created_indexes.append(
                {
                    "collection": collection_name,
                    "index": index_name,
                }
            )
    return created_indexes


def bootstrap_device_api_mongo_indexes():
    global _AUTO_INDEXES_BOOTSTRAPPED

    if _AUTO_INDEXES_BOOTSTRAPPED:
        return []

    _AUTO_INDEXES_BOOTSTRAPPED = True
    try:
        created = ensure_device_api_mongo_indexes()
        logger.info("Device API Mongo indexes ensured: %s", len(created))
        return created
    except Exception as exc:
        logger.warning("Device API Mongo indexes bootstrap skipped: %s", exc)
        return []
