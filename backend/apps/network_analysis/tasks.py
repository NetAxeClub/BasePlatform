import time

from celery import shared_task

from apps.network_analysis.services import (
    AddressTrackingAnalysisService,
    InterfaceUtilizationAnalysisService,
    NetworkAnalysisOrchestratorService,
)
from netaxe.celery import AxeTask


@shared_task(base=AxeTask, once={"graceful": True})
def refresh_interface_utilization(device_ip=None):
    return InterfaceUtilizationAnalysisService.refresh(device_ip=device_ip)


@shared_task(base=AxeTask, once={"graceful": True})
def refresh_address_tracking(ip_address=None):
    return AddressTrackingAnalysisService.refresh(ip_address=ip_address)


@shared_task(base=AxeTask, once={"graceful": True})
def refresh_network_analysis(manage_ip=None, ip_address=None, triggered_by="system"):
    return NetworkAnalysisOrchestratorService.refresh_all(
        manage_ip=manage_ip,
        ip_address=ip_address,
        triggered_by=triggered_by,
    )


@shared_task(base=AxeTask, once={"graceful": True})
def refresh_network_analysis_for_batch(
    execute_time,
    expected_devices=0,
    expected_subtasks=0,
    wait_seconds=15,
    max_attempts=20,
    triggered_by="device_api-batch",
):
    return NetworkAnalysisOrchestratorService.wait_and_refresh_batch(
        execute_time=execute_time,
        expected_devices=expected_devices,
        expected_subtasks=expected_subtasks,
        wait_seconds=wait_seconds,
        max_attempts=max_attempts,
        triggered_by=triggered_by,
    )
