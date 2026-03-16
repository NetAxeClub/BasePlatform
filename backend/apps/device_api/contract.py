"""device_api 标准化采集结果合同。"""

from apps.device_api.fields_mapping import COMMON_METADATA_FIELDS, DEFAULT_COLLECTION_TYPES


STANDARD_COLLECTION_CONTEXT_FIELDS = (
    "summary_plan_id",
    "plan_id",
    "collection_type",
    "collection_method",
    "execute_time",
)


REQUIRED_STANDARD_COLLECTION_FIELDS = COMMON_METADATA_FIELDS + STANDARD_COLLECTION_CONTEXT_FIELDS


STANDARD_PLAN_COLLECTIONS = tuple(
    f"plan_{collection_type}" for collection_type in DEFAULT_COLLECTION_TYPES
)
