import json
import logging
import os
import time
from datetime import datetime

from celery import shared_task

from apps.open_ipam.models import IpAddress, Subnet
from utils.db.mongo_ops import IpamMongoOps
from netaxe.settings import BASE_DIR
from utils.ipam_utils import IpAmForNetwork
from netaddr import IPNetwork
logger = logging.getLogger('ipam')
def write_log(filename, datas):
    try:
        isExists = os.path.exists(os.path.dirname(filename))
        if not isExists:
            os.makedirs(os.path.dirname(filename))
    except Exception as e:
        pass
    with open(filename, 'a', encoding='utf-8-sig') as f:
        for row in datas:
            f.write(row)
    logger.info('Write Log Done!')

@shared_task
def ip_am_update_sub_task(ip):
    ip_address_model = IpAddress
    # 文件名-操作失败的IP地址写入文件中
    file_time = datetime.now().strftime("%Y-%m-%d")
    # netops_ipam_ip_fail文件路径.log
    ip_am_ip_fail_file = os.path.join(BASE_DIR, 'media', 'ipam', "netops_ipam_ip_fail-{}.log".format(file_time))
    # 在ipam地址表取地址实例
    ip_address_instance = ip_address_model.objects.filter(ip_address=ip).values().first()

    tmp_description = {"Last Online Time": file_time, }
    lastOnlineTime = file_time

    # TODO 判断IP地址是否在Netops-IPAM中有记录

    # IP地址暂时不存在Netops-IPAM中 则不存在子网网段IP
    if ip_address_instance is None:
        # 网段不存在,则去判断16位存不存在,看是否需要先新增网段
        # TODO V6地址怎么查询上一级网段-目前策略直接跳过
        subnet16_id = IpAmForNetwork.get_sixteen_subnet_id(ip=ip)
        if subnet16_id:
            subnet24 = IPNetwork(f'{ip}/24').network
            # logger.info(subnet24)
            # 查询是否存在24位网段
            subnet24_instance = Subnet.objects.filter(subnet=str(subnet24) + "/24").first()
            if subnet24_instance:
                subnet_insert_id = subnet24_instance.id
            else:
                # 新建24位网段
                subnet_instance = Subnet(subnet=str(subnet24) + "/24", mask=24, master_subnet_id=subnet16_id,
                                         description=f'netops_ipam {file_time} 新建网段')
                subnet_instance.save()
                subnet_insert_id = subnet_instance.id

            """
            # 新增IP地址信息置位tag=4  未分配已使用
            1、查询除log_time字段外,是否有完全匹配,如果有就只更新log_time字段, 如果log_time字段一致,则不进行任何操作
            2、如果查询不到数据,则新增该字段
            """
            # TODO 到新增地址表
            IpamMongoOps.post_success_ip(ip)
            # 新建该IP地址实例、绑定IP地址插入的归属网段ID
            ip_create_instance = IpAddress(subnet_id=subnet_insert_id, ip_address=ip, tag=4,
                                           description=json.dumps(tmp_description))
            ip_create_instance.save()
        # 若不存在16位网段
        else:
            # 不存在16位网段-直接 TODO 丢弃到失败列表
            # TODO 新建16位网段、方便下一次任务更新地址成功
            if ip == '0.0.0.0':
                return
            subnet16 = IPNetwork(f'{ip}/16').network
            subnet_16_instance = Subnet(subnet=str(subnet16) + "/16", mask=16,
                                        description=f'netops_ipam {file_time} 新建16位网段')
            subnet_16_instance.save()
            logger.info('请先创建此网段：{}'.format(ip))
            IpamMongoOps.post_fail_ip(ip)
            _tmp_data = []
            _tmp_data.append(ip + '\n')
            write_log(ip_am_ip_fail_file, _tmp_data)

    # IP地址当前已经存在Netops-IPAM中
    # 取值tag并更新tag
    # 更新在线时间
    # 更新描述信息 取消
    else:
        ip_address_id = ip_address_instance['id']
        ip_address_tag = ip_address_instance['tag']
        ip_address_desc = ip_address_instance.get('description', '{}')
        if ip_address_tag == 6:  # 已分配未使用变更到 >>> 已分配已使用 update 最近在线时间、描述信息
            # TODO 更新 6 >>> 2
            IpamMongoOps.post_update_ip(ip)
            ip_update_6_instance = IpAddress.objects.get(id=ip_address_id)
            ip_update_6_instance.tag = 2
            ip_update_6_instance.lastOnlineTime = lastOnlineTime
            ip_update_6_instance.description = ip_address_desc if ip_address_desc else tmp_description

            ip_update_6_instance.save()
        if ip_address_tag == 7:  # 自定义空闲变更到 >>> 未分配已使用、最近在线时间、描述信息
            # TODO 更新 7 >>> 4
            IpamMongoOps.post_update_ip(ip)
            ip_update_7_instance = IpAddress.objects.get(id=ip_address_id)
            ip_update_7_instance.tag = 4
            ip_update_7_instance.lastOnlineTime = lastOnlineTime
            ip_update_7_instance.description = tmp_description

            ip_update_7_instance.save()
        else:  # 更新tag、最近在线时间、描述信息
            # TODO 更新 未使用-仅更新在线时间、描述信息
            IpamMongoOps.post_update_ip(ip)
            ip_update_else_instance = IpAddress.objects.get(id=ip_address_id)
            ip_update_else_instance.tag = ip_address_tag
            ip_update_else_instance.lastOnlineTime = lastOnlineTime
            ip_update_else_instance.description = ip_address_desc if ip_address_desc else tmp_description
            ip_update_else_instance.save()

    return


@shared_task
def ip_am_update_main():
    task_start_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    start_time = time.time()
    logger.info("IPAM信息更新开始:{}".format(task_start_time))
    file_time = datetime.now().strftime("%Y-%m-%d")
    # 获取tasks任务数量
    ip_am_update_tasks = []
    # 获取现网中所有IP地址 Total_ip_list
    total_ip = IpamMongoOps.get_total_ip()
    # 保留失败的地址
    ip_am_ip_fail_file = os.path.join(BASE_DIR, 'media', 'ipam', "netops_ipam_ip_fail-{}.log".format(file_time))

    # 删除旧mongo数据库
    if total_ip:
        IpamMongoOps.delet_coll(coll='netops_ipam_fail_ip')
        IpamMongoOps.delet_coll(coll='netops_ipam_success_ip')
        IpamMongoOps.delet_coll(coll='netops_ipam_update_ip')
    else:
        return
    # TODO 数据量很大导致任务很慢-优化执行逻辑
    for ip_info in total_ip:
        if ip_info['ipaddress']:
            # logger.info(ip_info['ipaddress'])
            # ip_am_update_sub_task(ip_info.get("ipaddress", "0.0.0.0"))
            ip_am_update_tasks.append(
                ip_am_update_sub_task.apply_async(args=(ip_info.get('ipaddress',"0.0.0.0"),)))
    logger.info("子任务下发完毕")

    # 等待子任务全部执行结束后执行下一步
    while len(ip_am_update_tasks) != 0:
        for tasks in ip_am_update_tasks:
            if tasks.ready():
                ip_am_update_tasks.remove(tasks)
    logger.info('子任务执行完毕')
    total_time = int((time.time() - start_time) / 60)
    logger.info('花费总时间' + str(total_time))

    ip_fail_counts = IpamMongoOps.get_coll_account(coll='netops_ipam_fail_ip')  # 失败地址表
    ip_add_counts = IpamMongoOps.get_coll_account(coll='netops_ipam_success_ip')  # 新增地址表
    ip_update_counts = IpamMongoOps.get_coll_account(coll='netops_ipam_update_ip')  # 更新地址表

    # 发送邮件和微信信息
    send_message = 'IPAM信息更新完成!\n新录入成功: {}个\n新录入失败: {}个\n更新成功: {}个\n总耗时: {}分钟\n'.format(
        ip_add_counts, ip_fail_counts, ip_update_counts, total_time)
    # 收件人邮箱
    email_addr = "xhweng2@iflytek.com"
    email_subject = 'IPAM信息更新结果_' + datetime.now().strftime("%Y-%m-%d %H:%M")
    email_text_content = send_message
    # if os.path.exists(ip_am_ip_fail_file):
    #     send_mail(receive_email_addr=email_addr, email_subject=email_subject,
    #               email_text_content=email_text_content, file_path=ip_am_ip_fail_file)
    # else:
    #     send_mail(receive_email_addr=email_addr, email_subject=email_subject, email_text_content=email_text_content)

    # 最后获取任务结束时间
    task_end_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    logger.info("发送微信、邮件完毕:{}".format(task_end_time))

    return

