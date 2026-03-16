import logging
import os
import sys

import pymongo

from apps.device_api import (
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
    interface_brief_mongo,
    ip_interface_mongo,
    isis_neighbors_mongo,
    lldp_mongo,
    mac_mongo,
    memory_status_mongo,
    ospf_interfaces_mongo,
    ospf_neighbors_mongo,
    power_status_mongo,
    route_table_mongo,
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
    "plan_device_identity": device_identity_mongo,
    "plan_arp": arp_mongo,
    "plan_mac": mac_mongo,
    "plan_lldp": lldp_mongo,
    "plan_ip_interface": ip_interface_mongo,
    "plan_interface_brief": interface_brief_mongo,
    "plan_aggre_port": aggre_port_mongo,
    "plan_fan_status": fan_status_mongo,
    "plan_power_status": power_status_mongo,
    "plan_temperature_status": temperature_status_mongo,
    "plan_cpu_status": cpu_status_mongo,
    "plan_memory_status": memory_status_mongo,
    "plan_board_status": board_status_mongo,
    "plan_transceiver_status": transceiver_status_mongo,
    "plan_storage_status": storage_status_mongo,
    "plan_environment_status": environment_status_mongo,
    "plan_clock_status": clock_status_mongo,
    "plan_route_table": route_table_mongo,
    "plan_bgp_neighbors": bgp_neighbors_mongo,
    "plan_bgp_summary": bgp_summary_mongo,
    "plan_ospf_neighbors": ospf_neighbors_mongo,
    "plan_ospf_interfaces": ospf_interfaces_mongo,
    "plan_isis_neighbors": isis_neighbors_mongo,
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
