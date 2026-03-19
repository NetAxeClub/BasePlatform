from dataclasses import asdict, dataclass
from typing import Dict, Optional

from apps.workflow_center.models import Tasks


@dataclass(frozen=True)
class ChangeTemplateSpec:
    code: str
    display_name: str
    category: str
    workflow_task: str
    risk_level: str = "low"
    supports_rollback: bool = True

    def to_summary_dict(self) -> Dict[str, object]:
        return asdict(self)


CHANGE_TEMPLATE_REGISTRY = {
    "sec_policy_low_risk": ChangeTemplateSpec(
        code="sec_policy_low_risk",
        display_name="低风险安全策略",
        category="security_policy",
        workflow_task=Tasks.SEC_POLICY,
    ),
    "address_object_low_risk": ChangeTemplateSpec(
        code="address_object_low_risk",
        display_name="低风险地址对象",
        category="address_object",
        workflow_task=Tasks.ADDRESS_SET,
    ),
    "service_object_low_risk": ChangeTemplateSpec(
        code="service_object_low_risk",
        display_name="低风险服务对象",
        category="service_object",
        workflow_task=Tasks.SERVICE_SET,
    ),
    "dnat_low_risk": ChangeTemplateSpec(
        code="dnat_low_risk",
        display_name="低风险 DNAT",
        category="dnat",
        workflow_task=Tasks.DNAT,
    ),
}


def get_change_template_spec(template_code: str) -> Optional[ChangeTemplateSpec]:
    return CHANGE_TEMPLATE_REGISTRY.get((template_code or "").strip())
