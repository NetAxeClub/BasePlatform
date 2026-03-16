"""device_api 标准化采集结果合同。"""

from apps.device_api.fields_mapping import COMMON_METADATA_FIELDS, DEFAULT_COLLECTION_TYPES


STANDARD_PLAN_COLLECTION_PREFIX = "plan_"

# version 仅作为 device_identity 的兼容处理别名保留，不单独占用标准结果集合。
STORAGE_COLLECTION_TYPE_ALIASES = {
    "version": "device_identity",
}


STANDARD_COLLECTION_CONTEXT_FIELDS = (
    "summary_plan_id",
    "plan_id",
    "collection_type",
    "collection_method",
    "execute_time",
)


REQUIRED_STANDARD_COLLECTION_FIELDS = COMMON_METADATA_FIELDS + STANDARD_COLLECTION_CONTEXT_FIELDS


def normalize_collection_type_for_storage(collection_type):
    """将采集类型归一到标准入库类型。"""
    normalized_type = str(collection_type or "").strip()
    return STORAGE_COLLECTION_TYPE_ALIASES.get(normalized_type, normalized_type)


def build_plan_collection_name(collection_type):
    """返回标准化结果集合名。"""
    normalized_type = normalize_collection_type_for_storage(collection_type)
    if not normalized_type:
        raise ValueError("collection_type 不能为空")
    return f"{STANDARD_PLAN_COLLECTION_PREFIX}{normalized_type}"


def freeze_collection_context(context):
    """冻结采集结果上下文字段，确保 collection_type 使用标准入库类型。"""
    raw_context = dict(context or {})
    raw_context["collection_type"] = normalize_collection_type_for_storage(
        raw_context.get("collection_type")
    )

    frozen_context = {
        field_name: raw_context.get(field_name, "")
        for field_name in STANDARD_COLLECTION_CONTEXT_FIELDS
    }
    for key, value in raw_context.items():
        frozen_context.setdefault(key, value)
    return frozen_context


STANDARD_PLAN_COLLECTIONS = tuple(
    build_plan_collection_name(collection_type) for collection_type in DEFAULT_COLLECTION_TYPES
)
