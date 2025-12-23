# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      tasks
   Description:     设备采集任务
   Author:          Junhu19
   date：           2024/01/01
-------------------------------------------------
   Change Activity:
                    2024/01/01
-------------------------------------------------

以前方案（automation/tasks.py）定时任务采集逻辑梳理：

一、主调度任务 collect_device_main(**kwargs)
   执行流程：
   1. datas_to_cache() - 将ARP、MAC、LLDP等表数据写入缓存（用于地址定位等功能）
   2. MainIn.cmdb_to_mongo() - 同步CMDB设备信息到MongoDB
   3. get_device_info_v2(**kwargs) - 获取所有符合条件的设备列表
      - 条件：status=0, auto_enable=True, 有采集方案(plan_id)
      - 返回设备信息（包含SSH/Netconf账号密码等）
   4. clear_his_collect_res() - 清空历史采集数据（MongoDB中的旧数据）
   5. 批量下发 collect_device 任务到 Celery 队列（queue='config'）

二、单个设备采集任务 collect_device(**kwargs)
   执行流程：
   1. 验证设备有效性（IP、采集方案、自动化启用状态）
   2. 根据厂商别名（vendor__alias）选择对应的处理类：
      - H3C -> H3cProc
      - Huawei -> HuaweiProc
      - Hillstone -> HillstoneProc
      - 等等...
   3. 实例化处理类，传入设备信息（包含plan_id）
   4. 调用 class_instance.collection_run() 执行采集

三、厂商处理类 collection_run() 方法（以H3cProc为例）
   执行流程：
   1. 调用父类 BaseConn.collection_run()：
      a. 从 CollectionPlan 获取 commands（JSON格式的命令列表）
      b. 使用 Netmiko 连接设备，执行命令
      c. 将命令输出保存到文件（automation/{hostip}/{cmd}.txt）
      d. 调用 _collection_analysis(paths) 解析数据
   2. 如果配置了 netconf_class，执行 NETCONF 采集：
      a. 根据 netconf_class 选择连接类（如 H3CinfoCollection）
      b. 从 CollectionPlan 获取 netconf_method（JSON格式的方法列表）
      c. 遍历执行每个 netconf 方法
      d. 调用 _netconf_method_map(method, res) 解析数据
   3. 将解析后的数据写入 MongoDB：
      - ARPTable、MACTable、layer2interface、layer3interface
      - AggreTable、LLDPTable、DNAT 等

四、数据解析流程
   1. CLI命令解析（_collection_analysis）：
      - 使用 TextFSM 模板解析命令输出
      - 调用 StandardFSMAnalysis 类的方法处理数据
      - 格式化后写入 MongoDB
   2. NETCONF数据解析（_netconf_method_map）：
      - 根据方法名映射到对应的解析函数
      - 处理XML数据，转换为结构化数据
      - 写入 MongoDB

五、采集方案模型（旧方案 automation.CollectionPlan）
   - vendor: 厂商
   - category: 设备类型（交换机/防火墙/路由器）
   - commands: JSON格式的命令列表，如 ["display arp", "display mac-address"]
   - netconf_method: JSON格式的方法列表，如 ["get_arp", "get_interface"]
   - netconf_class: NETCONF连接类名称，如 "H3CinfoCollection"

六、新方案（device_api）的改进
   - 使用 DeviceCollectionPlans（父方案）+ DeviceSubCollectionPlan（子方案）
   - 子方案支持独立的 Netmiko 和 NETCONF 配置
   - 通过南向驱动服务（south_gateway）统一执行采集
   - 支持字段映射和自定义数据处理
"""
from __future__ import absolute_import, unicode_literals
import logging
import time
import json
from celery import shared_task
from django.core.cache import cache
from django.db import connections
from apps.device_api.fields_mapping import field_mapping
from netaxe.celery import AxeTask
from apps.asset.models import NetworkDevice
from apps.device_api.services import DeviceCollectionService
from apps.device_api.tools.collect_device import get_auto_device
from apps.automation.cache_utils import cache_network_data
from apps.device_api import COLLECTION_SUB_PLAN
from apps.device_api import arp_mongo, mac_mongo, lldp_mongo, aggre_port_mongo
from utils.db.mongo_ops import MongoOps, MongoNetOps

logger = logging.getLogger("device_api")


def datas_to_cache():
    # 获取ARP表的所有数据 tables 用来汇总查询条件
    tables = {
        "plan_arp": {
            "_id": 0,
            "ipaddress": 1,
            "idc_name": 1,
            "hostip": 1,
            "macaddress": 1,
            "interface": 1,
        },
        "plan_mac": {
            "_id": 0,
            "idc_name": 1,
            "interface": 1,
            "hostip": 1,
            "macaddress": 1,
        },
        "plan_lldp": {
            "_id": 0,
            "neighborsysname": 1,
            "hostip": 1,
            "local_interface": 1,
            "neighbor_ip": 1,
        },
        "plan_aggre": {"_id": 0, "memberports": 1, "hostip": 1, "aggregroup": 1},
    }

    # arp 以 arp_ + ip 作为key
    def arp_to_cache():
        arp_res = arp_mongo.find(fields={"_id": 0, "log_time": 0})
        arp_result = dict()
        for _arp in arp_res:
            if _arp["ipaddress"] in arp_result.keys():
                arp_result[_arp["ipaddress"]].append(_arp)
            else:
                arp_result[_arp["ipaddress"]] = [_arp]
        for _arp in arp_result.keys():
            cache_key = ("device_arp", _arp)
            cache_network_data("arp_table", *cache_key, data=arp_result[_arp])

    # mac地址 以 idc + mac 地址作为key
    def mac_to_cache():
        # mac_mongo = MongoOps(db='Automation', coll='MACTable')
        mac_res = mac_mongo.find(fields=tables["plan_mac"])
        mac_result = dict()
        for _mac in mac_res:
            if _mac["idc_name"] + "_" + _mac["macaddress"] in mac_result.keys():
                mac_result[_mac["idc_name"] + "_" + _mac["macaddress"]].append(_mac)
            else:
                mac_result[_mac["idc_name"] + "_" + _mac["macaddress"]] = [_mac]
        for _mac in mac_result.keys():
            cache_key = ("device_mac", _mac)
            cache_network_data("mac_table", *cache_key, data=mac_result[_mac])

    # lldp 以 hostip local_interface 作为key
    def lldp_to_cache():
        lldp_res = lldp_mongo.find(fields=tables["plan_lldp"])
        lldp_result = dict()
        for _lldp in lldp_res:
            if _lldp["hostip"] + "_" + _lldp["local_interface"] in lldp_result.keys():
                lldp_result[_lldp["hostip"] + "_" + _lldp["local_interface"]].append(
                    _lldp
                )
            else:
                lldp_result[_lldp["hostip"] + "_" + _lldp["local_interface"]] = [_lldp]
        for _lldp in lldp_result.keys():
            cache.set("lldp_" + _lldp, json.dumps(lldp_result[_lldp]), 3600 * 12)
        # 反向
        reverse_lldp_result = dict()
        for _lldp in lldp_res:
            if _lldp["neighbor_ip"] is None:
                continue
            if not _lldp["neighbor_ip"]:
                continue
            if not _lldp.get("neighbor_port"):
                continue
            if (
                _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                in reverse_lldp_result.keys()
            ):
                reverse_lldp_result[
                    _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                ].append(_lldp)
            else:
                reverse_lldp_result[
                    _lldp["neighbor_ip"] + "_" + _lldp["neighbor_port"]
                ] = [_lldp]
        for _lldp in reverse_lldp_result.keys():
            cache.set(
                "lldp_reverse_" + _lldp,
                json.dumps(reverse_lldp_result[_lldp]),
                3600 * 12,
            )

    # lagg 以 hostip aggregroup 作为key
    def aggre_to_cache():
        lagg_res = aggre_port_mongo.find(fields=tables["plan_aggre"])
        lagg_result = dict()
        for _lagg in lagg_res:
            if _lagg["hostip"] + "_" + _lagg["aggregroup"] in lagg_result.keys():
                lagg_result[_lagg["hostip"] + "_" + _lagg["aggregroup"]].append(_lagg)
            else:
                lagg_result[_lagg["hostip"] + "_" + _lagg["aggregroup"]] = [_lagg]
        for _lagg in lagg_result.keys():
            cache.set("lagg_" + _lagg, json.dumps(lagg_result[_lagg]), 3600 * 12)

    content = ""
    init_time = time.time()
    arp_to_cache()
    content += "{}缓存耗时{}秒\n".format("ARP地址库", int(time.time() - init_time))

    start_time = time.time()
    mac_to_cache()
    content += "{}缓存耗时{}秒\n".format("MAC地址库", int(time.time() - start_time))

    # start_time = time.time()
    # lldp_to_cache()
    # content += "{}缓存耗时{}秒\n".format('LLDP库', int(time.time() - start_time))
    #
    # start_time = time.time()
    # aggre_to_cache()
    # content += "{}缓存耗时{}秒\n".format('聚合端口库', int(time.time() - start_time))

    content += "{}缓存耗时{}秒\n".format("总写入", int(time.time() - init_time))
    logger.debug(content)
    return


class MainIn:
    # CMDB 网络设备信息，并写Mongodb
    @staticmethod
    def cmdb_to_mongo():
        # 获取所有设备信息
        all_devs = (
            NetworkDevice.objects.select_related(
                "idc_model",
                "model",
                "role",
                "attribute",
                "category",
                "vendor",
                "idc",
                "framework",
                "zone",
                "rack",
            )
            .prefetch_related("bind_ip", "account")
            .filter(status=0)
            .values(
                "name",
                "idc__name",
                "serial_num",
                "manage_ip",
                "status",
                "chassis",
                "slot",
                "idc_model__name",
                "u_location_start",
                "u_location_end",
                "rack__name",
            )
        )
        MongoNetOps.post_cmdb(all_devs)
        return


def clear_his_collect_res():
    # 清空主采集任务记录
    # COLLECTION_PLAN.delete()

    # 清空子采集任务数据
    COLLECTION_SUB_PLAN.delete()

    # 清空采集到的采集类型数据表
    for collect_type in field_mapping.keys():
        MongoOps(db="Automation", coll=f"plan_{collect_type}").delete()
    return


@shared_task(base=AxeTask, once={"graceful": True})
def plan_collect_device(**kwargs):
    """
    单个设备采集任务
    执行设备关联的父采集方案下的所有子采集方案

    :param kwargs: 设备信息字典，包含 manage_ip, plan_id, sub_plans 等
                  sub_plans: 子采集方案列表（从get_auto_device传递过来，避免数据库查询）
    :return:
    """
    connections.close_all()
    host_ip = kwargs.get("manage_ip")  # 设备管理IP地址

    if not host_ip or host_ip == "0.0.0.0":
        logger.warning(f"设备IP无效: {host_ip}")
        return {}

    plan_id = kwargs.get("plan_id")
    if not plan_id:
        logger.warning(f"设备 {host_ip} 未关联数据采集方案")
        return {}

    try:
        # 使用从get_auto_device传递过来的子采集方案列表
        sub_plans_list = kwargs.get("sub_plans", [])

        if not sub_plans_list:
            logger.warning(
                f"设备 {host_ip} 关联的采集方案不存在、已禁用或没有子采集方案: plan_id={plan_id}"
            )
            return {}

        logger.info(f"开始采集设备 {host_ip}, 子方案数量: {len(sub_plans_list)}")

        # 在执行采集之前，插入主采集方案记录
        DeviceCollectionService.insert_parent_plan_data(
            plan=sub_plans_list[0],
            device_info=kwargs,
            sub_plans_count=len(sub_plans_list),
        )

        for sub_plan in sub_plans_list:
            try:
                logger.info(f"执行子采集方案: {sub_plan['name']} (设备: {host_ip})")

                # 执行采集（同时执行NETCONF和Netmiko）
                result = DeviceCollectionService.celery_both_collection(
                    plan=sub_plan, device_info=kwargs
                )

                if result.get("success"):
                    logger.info(
                        f"子采集方案执行成功: {sub_plan['name']} (设备: {host_ip})"
                    )
                else:
                    error_msg = result.get("error", "未知错误")
                    logger.error(
                        f"子采集方案执行失败: {sub_plan['name']} (设备: {host_ip}), 错误: {error_msg}"
                    )

            except Exception as e:
                logger.error(
                    f"执行子采集方案异常: {sub_plan['name']} (设备: {host_ip}), 异常: {str(e)}",
                    exc_info=True,
                )

        logger.info(f"设备 {host_ip} 采集完成, 总计: {len(sub_plans_list)}")

        return {"host_ip": host_ip, "total": len(sub_plans_list)}

    except Exception as e:
        logger.error(f"设备采集任务异常: {host_ip}, 异常: {str(e)}", exc_info=True)
        return {}


# 通用信息采集主调度任务
@shared_task(base=AxeTask, once={"graceful": True})
def plan_collect_device_main(**kwargs):
    logger.info("开始执行设备信息采集主调度任务")
    datas_to_cache()  # 将数据写入缓存
    logger.info("数据缓存更新完成")

    # 同步CMDB设备信息到MongoDB
    try:
        MainIn.cmdb_to_mongo()
        logger.info("CMDB设备信息已同步到MongoDB")
    except Exception as e:
        logger.warning(f"同步CMDB设备信息到MongoDB失败: {str(e)}")

    # 获取设备列表
    if kwargs:
        # 如果有过滤条件，使用过滤条件获取设备
        hosts = get_auto_device(**kwargs)
    else:
        # 获取所有符合条件的设备（status=0, auto_enable=True, 有采集方案）
        hosts = get_auto_device()

    logger.info(f"获取所有设备信息结束，获取到 {len(hosts)} 个设备信息")

    # 参数初始化
    net_tower_tasks = []  # 采集任务id集合

    # 清空历史采集数据
    try:
        clear_his_collect_res()
        logger.info("历史采集数据已清空")
    except Exception as e:
        logger.warning(f"清空历史采集数据失败: {str(e)}")
        return

    start_time = time.time()

    # 批量下发任务
    for host in hosts:
        host_ip = host.get("manage_ip")
        task = plan_collect_device.apply_async(kwargs=host, queue="config", retry=True)
        net_tower_tasks.append(task)
        logger.debug(f"已下发采集任务: {host_ip}, task_id: {task.id}")

    logger.info("批量下发任务结束")
    total_time = (time.time() - start_time) / 60
    logger.info(
        f"批量下发任务完成, 总设备数: {len(hosts)}, 有效任务: {len(net_tower_tasks)}, 耗时: {total_time:.2f}分钟"
    )

    return {
        "total": len(hosts),
        "tasks": len(net_tower_tasks),
        "time_cost": f"{total_time:.2f}分钟",
    }


@shared_task(base=AxeTask, once={"graceful": True})
def batch_update_device_name_by_snmp(**kwargs):
    """
    批量通过SNMP探测更新设备名称
    遍历所有NetworkDevice，根据SNMP配置进行探测，将获取到的system name填入name字段

    :param kwargs: 可选参数
        - device_ids: 指定设备ID列表，如果提供则只处理这些设备
        - skip_empty_snmp: 是否跳过SNMP配置为空的设备，默认True
    :return: 处理结果统计
    """
    from utils.connect_layer.snmp.snmp_test import probe_snmp

    connections.close_all()

    # 获取过滤条件
    # 构建查询
    queryset = NetworkDevice.objects.filter(**kwargs)

    # 统计信息
    total_count = queryset.count()
    success_count = 0
    failed_count = 0
    skipped_count = 0
    updated_count = 0

    logger.info(f"开始批量SNMP探测更新设备名称，总设备数: {total_count}")

    # 遍历所有设备
    for device in queryset.iterator(chunk_size=100):
        try:
            # 检查SNMP配置
            if not device.snmp_community or device.snmp_community == "-":
                skipped_count += 1
                logger.debug(f"设备 {device.manage_ip} SNMP团体字为空，跳过")
                continue

            if not device.snmp_version:
                skipped_count += 1
                logger.debug(f"设备 {device.manage_ip} SNMP版本为空，跳过")
                continue

            # 检查IP地址
            if not device.manage_ip or device.manage_ip == "0.0.0.0":
                skipped_count += 1
                logger.debug(f"设备 {device.id} 管理IP无效，跳过")
                continue

            # 调用SNMP探测
            logger.info(
                f"开始探测设备: {device.manage_ip}, SNMP版本: {device.snmp_version}, 团体字: {device.snmp_community}"
            )

            success, result = probe_snmp(
                ip=device.manage_ip,
                snmp_version=device.snmp_version,
                snmp_community=device.snmp_community,
                port=device.snmp_port,
                timeout=5,
                retries=1,
            )

            if success:
                success_count += 1
                # result 是 system_name
                if result and result.strip():
                    # 更新设备名称
                    old_name = device.name
                    device.name = result.strip()
                    device.snmp_status = True
                    device.save(update_fields=["name", "snmp_status"])
                    updated_count += 1
                    logger.info(
                        f"设备 {device.manage_ip} SNMP探测成功，system name: {result}, 已更新name字段 (旧值: {old_name})"
                    )
                else:
                    # SNMP连接成功但没有获取到system name
                    device.snmp_status = True
                    device.save(update_fields=["snmp_status"])
                    logger.warning(
                        f"设备 {device.manage_ip} SNMP探测成功但未获取到system name"
                    )
            else:
                failed_count += 1
                device.snmp_status = False
                device.save(update_fields=["snmp_status"])
                logger.warning(f"设备 {device.manage_ip} SNMP探测失败: {result}")

        except Exception as e:
            failed_count += 1
            logger.error(
                f"设备 {device.manage_ip} (ID: {device.id}) SNMP探测异常: {str(e)}",
                exc_info=True,
            )
            try:
                device.snmp_status = False
                device.save(update_fields=["snmp_status"])
            except:
                pass

    # 汇总结果
    result_summary = {
        "total": total_count,
        "success": success_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "updated": updated_count,
    }

    logger.info(f"批量SNMP探测完成，统计: {result_summary}")

    return result_summary
