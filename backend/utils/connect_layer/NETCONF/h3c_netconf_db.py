#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import logging
from utils.connect_layer.NETCONF.netconf_connect import H3CNetconf, XmlToDict

logger = logging.getLogger(__name__)


class H3CinfoCollectionDB(H3CNetconf):
    """基于数据库的H3C NETCONF信息采集类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = 'H3C'
        self.device_type = kwargs.get('device_type', 'switch')

    @staticmethod
    def get_method():
        """获取支持的方法列表"""
        return [
            'collection_vrf_list',
            'collection_l2vpn_vsis',
            'collection_test_mac',
            'collection_mac_over_evpn',
            'collection_arp_over_evpn',
            'collection_ipv4_routetable',
            'collection_running_config',
            'collection_interface_info',
            'collection_filesystem_info',
            'collection_startup_file__info',
            'collection_ntp_status_info',
            'collection_address_number_info',
            'collection_acl_resource_info',
            'collection_http_https_status_info',
            'collection_stp_status_info',
            'collection_ftp_status_info',
            'collection_snmp_version_info',
            'collection_local_user_hash_info',
            'collection_irf_info',
            'collection_logbuffer_summary_info',
            'collection_interfaceinfo',
            'collection_yang_info',
            'save_running_config',
            'rollback_config',
            'collection_ipv4staticroute',
            'collection_snmpconfig',
            'collection_BGP_config',
            'collection_ACL_config',
            'collection_arp_vsi',
            'patch_version',
            'get_global_nat_policy',
            'get_netaddr_pool',
            'nat_dynamic_rules',
            'nat_static_mapping',
            'nat_policy',
            'nat_server_group',
            'nat_object_server',
            'get_sec_policy',
            'get_ipv4_group',
            'get_ipv4_objs',
            'get_ipv4_paging',
            'get_sec_zone',
            'get_server_groups',
            'get_ipv4_routes'
        ]

    # 以下是所有方法的实现，每个方法都调用_execute_netconf_method
    
    def collection_vrf_list(self, **kwargs):
        """采集VRF列表"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("VRF列表采集需要XML模板配置")
        
        # 根据业务逻辑决定执行哪些XML模板
        data_xml = xml_templates[0].xml_template
    
        request_arplist = self.netconf_get(data_xml)["top"]['L3vpn']['L3vpnVRF']['VRF']
        return request_arplist

    def collection_l2vpn_vsis(self, **kwargs):
        """采集L2VPN VSIs"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("L2VPN VSIs采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        req = self.netconf_get(data_xml)['top']
        if req:
            vsis = req['L2VPN']['VSIs']['VSI']
            # print(req['L2VPN'].keys())
            ACs = req['L2VPN']['ACs']['AC']
            ifmgrlist = req['Ifmgr']['Interfaces']['Interface']
            # SRVs = req['L2VPN']['SRVs']['SRV']
            for a in vsis:
                for b in ACs:
                    if a['VsiName'] == b['VsiName']:
                        a.update(IfIndex=b['IfIndex'], SrvID=b['SrvID'])
            for a in vsis:
                for b in ifmgrlist:
                    if 'IfIndex' in a.keys():
                        if a['IfIndex'] == b['IfIndex']:
                            a.update(Name=b['Name'])
            return vsis
        else:
            return []

    def collection_test_mac(self, **kwargs):
        """采集测试MAC"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("MAC测试采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        res = self.netconf_get(data_xml)['top']
        return res            
      
    def collection_mac_over_evpn(self, **kwargs):
        """采集EVPN MAC"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("EVPN MAC采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)
        if 'top' in res:
            res = res['top']
            if 'L2VPN' not in res.keys():
                return []
            mac_list = res['L2VPN']['LocalMACs']['MAC']
            # 接口索引和name对应
            ifmgrlist = res['Ifmgr']['Interfaces']['Interface']
            # 两个表格合并，将name加入arp表格
            if isinstance(mac_list, dict):
                mac_list = [mac_list]
            for a in mac_list:
                for b in ifmgrlist:
                    if a['IfIndex'] == b.get('IfIndex'):
                        a.update(PortName=b['Name'])
            return mac_list
        else:
            return []
    
    def collection_arp_over_evpn(self, **kwargs):
        """采集EVPN ARP"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("EVPN ARP采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        if res:
            if 'L2VPN' not in res.keys():
                return []
            arplist = res['ARP']['ArpTable']['ArpEntry']
            mac_list = res['L2VPN']['LocalMACs']['MAC']
            # 接口索引和name对应
            ifmgrlist = res['Ifmgr']['Interfaces']['Interface']
            # 两个表格合并，将name加入arp表格
            if isinstance(arplist, dict):
                arplist = [arplist]
            if isinstance(mac_list, dict):
                mac_list = [mac_list]
            for a in arplist:
                for b in mac_list:
                    if a['MacAddress'] == b.get('MacAddr'):
                        a['IfIndex'] = b['IfIndex']
            for a in arplist:
                for b in ifmgrlist:
                    if a['IfIndex'] == b['IfIndex']:
                        a.update(Name=b['Name'])
            for a in arplist:
                for b in ifmgrlist:
                    if a.get('PortIndex'):
                        if a['PortIndex'] == b.get('PortIndex'):
                            a['Name'] = b['Name']

            return arplist
        else:
            return []
    
    def collection_ipv4_routetable(self, **kwargs):
        """采集IPv4路由表"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("IPv4路由表采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        request_info = self.netconf_get(data_xml)
        if request_info != 'None':
            request_info = request_info['top']['Route']['Ipv4Routes']['RouteEntry']
        return request_info

    def collection_running_config(self, **kwargs):
        """采集运行配置"""
        request_info = self.netconfig_get_config()
        return request_info['top']
    
    def collection_interface_info(self, **kwargs):
        """采集接口信息"""
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("接口信息采集需要XML模板配置")

        obtain_h3c_display_interface_xml = xml_templates[0].xml_template

        request_info = self.netconf_cli(obtain_h3c_display_interface_xml)
        response_info = [x for x in str(request_info).strip().splitlines() if x != ''
                         if x != '<ncclient-test>display interface GigabitEthernet'
                         if x != '<ncclient-test>display interface Ten-GigabitEthernet']
        # 排序
        cnt = 0
        index_port_name_lst = []
        interface_info_dict = {}
        for i in response_info:
            result_1 = re.match('(GigabitEthernet|Ten-GigabitEthernet)(.*)', i, re.IGNORECASE)
            if result_1:
                index_port_name_lst.append(cnt)
            cnt += 1
        else:
            index_port_name_lst.append(-1)
        index_range_lst = [list(x) for x in zip(index_port_name_lst[:-1], index_port_name_lst[1:])]
        if self.device_type == "switch":
            for i in index_range_lst:
                # 判断当前接口状态：UP or DOWN
                if response_info[i[0]:i[1]][1].split('state:')[1].strip() == 'UP':
                    dict_key = ''
                    dict_values = []
                    input_info = []
                    output_info = []
                    for j in response_info[i[0]:i[1]]:
                        j = str(j).strip()
                        if re.match('(GigabitEthernet|Ten-GigabitEthernet)(.*)', j, re.IGNORECASE):
                            dict_key = j
                        elif re.match('(Current state:)(.*)', j, re.IGNORECASE):
                            dict_values.append(j)
                        elif re.match('(Link speed type is)(.*)', j, re.IGNORECASE):
                            dict_values.append(j.split(', ')[0].strip())
                            dict_values.append(j.split(', ')[1].strip())
                        elif re.match('\\d(.*)(speed mode,)(.*)', j, re.IGNORECASE):
                            dict_values.append(j.split(', ')[0].strip())
                            dict_values.append(j.split(', ')[1].strip())
                        elif re.match('Input:(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split('Input:')[1].strip().split(', '))
                        elif re.match('\\d(.*)CRC,(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split(', '))
                        elif re.match('(.*)ignored,(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split(', '))
                        elif re.match('Output:', j, re.IGNORECASE):
                            output_info.extend(j.split('Output:')[1].strip().split(', '))
                        elif re.match('\\d(.*)aborts', j, re.IGNORECASE):
                            output_info.extend(j.strip().split(', '))
                        elif re.match('\\d(.*)lost carrier', j, re.IGNORECASE):
                            output_info.extend(j.strip().split(', '))
                    dict_values.append({'Input_Error': input_info})
                    dict_values.append({'Output_Error': output_info})
                    interface_info_dict[dict_key] = dict_values
                else:
                    continue
        else:
            for i in index_range_lst:
                # 判断当前接口状态：UP or DOWN
                if response_info[i[0]:i[1]][1].split('state:')[1].strip() == 'UP':
                    dict_key = ''
                    dict_values = []
                    input_info = []
                    output_info = []
                    for j in response_info[i[0]:i[1]]:
                        j = str(j).strip()
                        if re.match('(GigabitEthernet|Ten-GigabitEthernet)(.*)', j, re.IGNORECASE):
                            dict_key = j
                        elif re.match('(Current state:)(.*)', j, re.IGNORECASE):
                            dict_values.append(j)
                        elif re.match(r'\d+Mbps, .*link type is .*', j):
                            dict_values.append(j.split(",")[0])
                            dict_values.append(j.split(",")[1])
                            dict_values.append(j.split(",")[2])
                        elif re.match('Input:(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split('Input:')[1].strip().split(', '))
                        elif re.match('\\d(.*)CRC,(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split(', '))
                        elif re.match('(.*)ignored,(.*)', j, re.IGNORECASE):
                            input_info.extend(j.split(', '))
                        elif re.match('Output:', j, re.IGNORECASE):
                            output_info.extend(j.split('Output:')[1].strip().split(', '))
                        elif re.match('\\d(.*)aborts', j, re.IGNORECASE):
                            output_info.extend(j.strip().split(', '))
                        elif re.match('\\d(.*)lost carrier', j, re.IGNORECASE):
                            output_info.extend(j.strip().split(', '))
                    dict_values.append({'Input_Error': input_info})
                    dict_values.append({'Output_Error': output_info})
                    interface_info_dict[dict_key] = dict_values
                else:
                    continue
        return interface_info_dict

    def collection_filesystem_info(self, **kwargs):
        """采集文件系统信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("文件系统信息采集需要XML模板配置")
        
        if len(xml_templates) < 2:
            raise ValueError("文件系统信息采集需要至少2个XML模板")
        
        obtain_h3c_file_system_info_xml = xml_templates[0].xml_template
        obtain_h3c_dir_xml = xml_templates[1].xml_template

        if self.device_type == 'switch':
            request_info = self.netconf_get(obtain_h3c_file_system_info_xml)
            request_info = request_info["top"]["FileSystem"]["Partitions"]["Partition"]
        else:
            request_info = self.netconf_cli(obtain_h3c_dir_xml)

        return request_info
    
    def collection_startup_file__info(self, **kwargs):
        """采集启动文件信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("启动文件信息采集需要XML模板配置")
        
        obtain_h3c_startup_file_info_xml = xml_templates[0].xml_template
        
        request_info = self.netconf_cli(obtain_h3c_startup_file_info_xml)
        return request_info
    
    def collection_ntp_status_info(self, **kwargs):
        """
        请求的XML命令
        """
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("NTP状态信息采集需要XML模板配置")
        
        if len(xml_templates) < 3:
            raise ValueError("NTP状态信息采集需要至少3个XML模板")
        
        obtain_h3c_ntp_enable_info_xml = xml_templates[0].xml_template
        obtain_h3c_ntp_sync_status_info_xml = xml_templates[1].xml_template
        obtain_h3c_device_local_time_info_xml = xml_templates[2].xml_template
        
        request_ntp_enable = self.netconf_get(obtain_h3c_ntp_enable_info_xml)["top"]['NTP']['Service']['NTPEnable']
        request_ntp_sync_status = self.netconf_get(obtain_h3c_ntp_sync_status_info_xml)
        request_ntp_sync_status = request_ntp_sync_status["top"]['NTP']['Status']['NTPSynchronized']
        request_device_local_time = self.netconf_get(obtain_h3c_device_local_time_info_xml)
        request_device_local_time = str(request_device_local_time["top"]['Device']['Base']['LocalTime']).replace('T',
                                                                                                                 ' ')
        request_ntp_info = [request_ntp_enable] + [request_ntp_sync_status] + [request_device_local_time]
        return request_ntp_info
    
    def collection_address_number_info(self, **kwargs):
        """采集地址数量信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("地址数量信息采集需要XML模板配置")
        
        if len(xml_templates) < 2:
            raise ValueError("地址数量信息采集需要至少2个XML模板")
        
        obtain_h3c_display_interface_xml = xml_templates[0].xml_template
        obtain_h3c_route_display_interface_xml = xml_templates[1].xml_template
        
        results = []
        a = 0
        b = 0
        if self.device_type == 'switch':
            request_info = str(self.netconf_cli(obtain_h3c_display_interface_xml)).splitlines()
            for i in request_info:
                # 活跃单播MAC地址统计
                if re.match(r'Total\sUnicast\sMAC\sAddresses\sIn\sUse:', i, re.IGNORECASE):
                    results.append(int(i.split(':')[1].strip()))
                # 单播MAC地址最大可用限制
                elif re.match(r'Total\sUnicast\sMAC\sAddresses\sAvailable:', i, re.IGNORECASE):
                    results.append(int(i.split(':')[1].strip()))
                # 组播MAC地址数统计
                elif re.match(r'Multicast\sand\sMultiport\sMAC\sAddress\sCount:', i, re.IGNORECASE):
                    a = int(i.split(':')[1].strip())
                # 静态组播MAC地址数统计
                elif re.match(r'Static Multicast and Multiport MAC Address (.*) Count: ', i, re.IGNORECASE):
                    b = int(i.split(':')[1].strip())
                # 组播MAC地址最大可用限制
                elif re.match(r'Total Multicast and Multiport MAC Addresses Available:', i, re.IGNORECASE):
                    results.append(a + b)
                    results.append(int(i.split(':')[1].strip()))
                # ARP静态地址数量
                elif re.match(r'Total\snumber\sof\sstatic\sentries:', str(i).strip(), re.IGNORECASE):
                    results.append(int(i.split()[-1]))
                # ARP动态地址数量
                elif re.match(r'Total\snumber\sof\sdynamic\sentries:', str(i).strip(), re.IGNORECASE):
                    results.append(int(i.split()[-1]))
                # 活跃路由表数量
                elif re.search(r'Total\s.*Active\sprefixes:\s\d+', i, re.IGNORECASE):
                    results.append(int(i.split('Active prefixes:')[1].strip()))
        else:
            request_info = str(self.netconf_cli(obtain_h3c_route_display_interface_xml)).splitlines()
            for i in request_info:
                # MAC地址数统计
                match_mac_cnt = re.match(r'(\d+\smac\saddress.*\sfound.)', i.strip(), re.I)
                if match_mac_cnt:
                    # 格式：静态MAC,动态MAC,组播MAC
                    results.append(match_mac_cnt.group().split()[0])
                # ARP地址数量
                match_arp_cnt = re.match(r'Total\snumber\sof\s.*\sentries:\s+\d+', i.strip(), re.I)
                if match_arp_cnt:
                    # 格式：静态ARP,动态ARP
                    results.append(match_arp_cnt.group().split()[-1])
                # 活跃路由表数量
                match_route_cnt = re.match(r'(Total(\s+\d+).*)', i.strip(), re.I)
                if match_route_cnt:
                    results.append(match_route_cnt.group().split()[2])
        return results
    
    def collection_acl_resource_info(self, **kwargs):
        """采集ACL资源信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("ACL资源信息采集需要XML模板配置")
        
        obtain_h3c_display_qos_acl_resource_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_qos_acl_resource_xml)).splitlines()
        request_info_dict = dict()
        key_name = None
        acl_resource_use_info = None
        for i in request_info:
            if re.match('Interfaces:.*', i.strip(), re.IGNORECASE):
                request_info_dict[i] = ''
                key_name = i
            elif re.match('IFP ACL.*%$', i.strip(), re.IGNORECASE):
                acl_resource_use_info = [i.strip().split()[-1]]
            elif re.match('EFP ACL.*%$', i.strip(), re.IGNORECASE):
                acl_resource_use_info += [i.strip().split()[-1]]
            if key_name is not None:
                request_info_dict[key_name] = acl_resource_use_info
        return request_info_dict
    
    def collection_http_https_status_info(self, **kwargs):
        """采集HTTP/HTTPS状态信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("HTTP/HTTPS状态信息采集需要XML模板配置")
        
        obtain_h3c_display_http_https_status_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_http_https_status_xml)).splitlines()
        return request_info
    
    def collection_stp_status_info(self, **kwargs):
        """采集STP状态信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("STP状态信息采集需要XML模板配置")
        
        obtain_h3c_display_stp_brief_status_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_stp_brief_status_xml)).splitlines()
        return request_info
    
    def collection_ftp_status_info(self, **kwargs):
        """采集FTP状态信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("FTP状态信息采集需要XML模板配置")
        
        obtain_h3c_display_ftp_status_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_ftp_status_xml)).splitlines()
        return request_info
    
    def collection_snmp_version_info(self, **kwargs):
        """采集SNMP版本信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("SNMP版本信息采集需要XML模板配置")
        
        obtain_h3c_display_snmp_running_version_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_snmp_running_version_xml)).splitlines()
        return request_info
    
    def collection_local_user_hash_info(self, **kwargs):
        """采集本地用户哈希信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("本地用户哈希信息采集需要XML模板配置")
        
        obtain_h3c_display_local_user_hash_xml = xml_templates[0].xml_template
        
        request_info = str(self.netconf_cli(obtain_h3c_display_local_user_hash_xml)).splitlines()
        lst = []
        user_info = None
        for i in request_info:
            if i == '' or i == '#' or i == 'return':
                continue
            else:
                i = i.strip().split()
                if i[0] == 'local-user':
                    user_info = i[1]
                elif i[0] == 'password':
                    lst.append((user_info, i[1]))
        return lst
    
    def collection_irf_info(self, **kwargs):
        """采集IRF信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("IRF信息采集需要XML模板配置")
        
        # obtain_h3c_irf_bfd_info_xml = xml_templates[0].xml_template
        obtain_h3c_irf_info_xml = xml_templates[0].xml_template

        role_map = {'1': 'Master', '2': 'Standby', '3': 'Loading', '4': 'Other'}
        req = self.netconf_get(obtain_h3c_irf_info_xml)
        if req:
            request_irf_info = req["top"]['IRF']['Members']['Member']
            if isinstance(request_irf_info, list):
                for i in request_irf_info:
                    if isinstance(i['Board'], list):
                        for _i in i['Board']:
                            _i['Role'] = role_map[_i['Role']]
                    elif isinstance(i['Board'], dict):
                        i['Board']['Role'] = role_map[i['Board']['Role']]
                return request_irf_info
            else:
                if 'Board' in request_irf_info.keys():
                    request_irf_info['Board']['Role'] = role_map[request_irf_info['Board']['Role']]
                    return [request_irf_info]
                else:
                    return []
        else:
            return []
    
    def collection_logbuffer_summary_info(self, **kwargs):
        """采集日志缓冲区摘要信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("日志缓冲区摘要信息采集需要XML模板配置")
        
        obtain_h3c_display_logbuffer_summary_xml = xml_templates[0].xml_template
        
        request_info = self.netconf_cli(obtain_h3c_display_logbuffer_summary_xml)
        return request_info
    
    def collection_interfaceinfo(self, **kwargs):
        """采集接口信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("接口信息采集需要XML模板配置")
        
        obtain_h3c_interfaceinfo_xml = xml_templates[0].xml_template
        
        request_info = self.netconf_get(obtain_h3c_interfaceinfo_xml)['top']['Ifmgr']['Interfaces']['Interface']
        return request_info

    def collection_yang_info(self, **kwargs):
        """采集YANG信息"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("YANG信息采集需要XML模板配置")
        
        yang_xml = xml_templates[0].xml_template
        
        request_info = self.netconf_get(yang_xml)['netconf-state']['schemas']['schema']
        return request_info
    
    def save_running_config(self, **kwargs):
        """保存运行配置"""
        request_info = self.save_config()
        return request_info

    def rollback_config(self, **kwargs):
        """回滚配置"""
        request_info = self.rollback()
        return request_info
    
    def collection_ipv4staticroute(self, **kwargs):
        """采集IPv4静态路由"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("IPv4静态路由采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        request = self.netconf_get(data_xml)["top"]['StaticRoute']['Ipv4StaticRouteConfigurations']['RouteEntry']
        return request
    
    def collection_snmpconfig(self, **kwargs):
        """采集SNMP配置"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("SNMP配置采集需要XML模板配置")
        
        system_xml = xml_templates[0].xml_template

        request = self.netconf_get(system_xml)["top"]['SNMP']['System']
        return request
    
    def collection_BGP_config(self, **kwargs):
        """采集BGP配置"""
        # 获取传入的XML模板列表
        xml_templates = kwargs.get('xml_templates', [])
        
        if not xml_templates:
            raise ValueError("BGP配置采集需要XML模板配置")
        
        if len(xml_templates) < 7:
            raise ValueError("BGP配置采集需要至少7个XML模板")
        
        instance_xml = xml_templates[0].xml_template
        vrfs_xml = xml_templates[1].xml_template
        CfgSessionGroups_xml = xml_templates[2].xml_template
        CfgSessions_xml = xml_templates[3].xml_template
        Sessions_xml = xml_templates[4].xml_template
        head_xml = xml_templates[5].xml_template
        tail_xml = xml_templates[6].xml_template

        xml = head_xml + instance_xml + vrfs_xml + CfgSessionGroups_xml + CfgSessions_xml + Sessions_xml + tail_xml
        res = self.netconf_get(xml)["top"]['BGP']
        
        # 处理BGP配置数据
        if 'Instances' in res and 'Instance' in res['Instances']:
            tmp = res['Instances']['Instance']
            for key, value in tmp.items():
                logger.debug(f'BGP Instance {key}: {value}')
        
        if 'VRFs' in res and 'VRF' in res['VRFs']:
            tmp = res['VRFs']['VRF']
            for key, value in tmp.items():
                logger.debug(f'BGP VRF {key}: {value}')
        
        if 'CfgSessions' in res and 'CfgSession' in res['CfgSessions']:
            tmp = res['CfgSessions']['CfgSession']
            for i in tmp:
                logger.debug(f'BGP CfgSession: {i}')
        
        if 'Sessions' in res and 'Session' in res['Sessions']:
            tmp = res['Sessions']['Session']
            for i in tmp:
                logger.debug(f'BGP Session: {i}')
        
        return res
    
    def collection_ACL_config(self, **kwargs):
        """采集ACL配置"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("ACL配置采集需要XML模板配置")
        
        if len(xml_templates) < 3:
            raise ValueError("ACL配置采集需要至少3个XML模板")
        
        Capability_xml = xml_templates[0].xml_template
        head_xml = xml_templates[1].xml_template    
        tail_xml = xml_templates[2].xml_template

        xml = head_xml + Capability_xml + tail_xml
        res = self.netconf_get(xml)["top"]['ACL']
        return res
    
    def collection_arp_vsi(self, **kwargs):
        """采集ARP VSI"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("ARP VSI采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        if res:
            return res["top"]['L2VPN']['VSIIpv4Subnets']['Ipv4Subnet'] 
        else:
            return []
    
    def patch_version(self, **kwargs):
        """获取补丁版本"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("补丁版本采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        if res:
            return res["top"]['Package']['ImageLists']['ImageList']
        else:
            return []
    
    def get_global_nat_policy(self, mode='DNAT', name='', **kwargs):
        """获取全局NAT策略"""
        """
        10.254.12.100 不支持 <TransSrcIP> (<Rule>下)
        :param mode:
        :return:
        """
        if self.netconf_dict['device_params']['name'] == "hpcomware":
            return []
        # 默认获取DNAT
        if mode == 'DNAT':
            TransMode = '1'  # DNAT
        else:
            TransMode = '0'  # SNAT
        
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("补丁版本采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get_bulk(data_xml)
        if res:
            if 'NAT' in res['top'].keys():
                trans_mode_map = {
                    '0': 'SNAT',
                    '1': 'DNAT',
                }
                return res['top']['NAT']['GlobalPolicyRuleMembers']['Rule']
        return []

    def get_netaddr_pool(self, **kwargs):
        """获取网络地址池"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("网络地址池采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def nat_dynamic_rules(self, **kwargs):
        """获取NAT动态规则"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT动态规则采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def nat_static_mapping(self, **kwargs):
        """获取NAT静态映射"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT静态映射采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def nat_policy(self, **kwargs):
        """获取NAT策略"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT策略采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def nat_server_group(self, **kwargs):
        """获取NAT服务器组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT服务器组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def nat_object_server(self, **kwargs):
        """获取NAT对象服务器"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT对象服务器采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        return self.netconf_get(data_xml)
    
    def get_sec_policy(self, **kwargs):
        """获取安全策略"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略采集需要XML模板配置")
        
        data_xml_1 = xml_templates[0].xml_template
        data_xml_2 = xml_templates[1].xml_template

        try:
            res = self.netconf_get_bulk(data_xml_1)['top']
        except Exception as e:
            logger.error(f"安全策略采集失败，尝试备用方法: {e}")    
            res = self.netconf_get(data_xml_2)
            if not res:
                return False
            else:
                res = res['top']
        if 'SecurityPolicies' not in res.keys():
            return False
        if res:
            type_map = {'1': 'IPv4', '2': 'IPv6'}
            action_map = {'1': 'Deny', '2': 'Permit'}
            result = res['SecurityPolicies']['GetRules']['Rule']
            if isinstance(result, dict):
                result = [result]
            for i in result:
                i['Type'] = type_map[i['Type']]
                i['Action'] = action_map[i['Action']]
            return result
        else:
            return False

    def get_ipv4_group(self, name="", **kwargs):
        """获取IPv4组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        
        res = self.netconf_get(data_xml)['top']
        if res:
            if isinstance(res['OMS']['IPv4Groups']['Group'], dict):
                return [res['OMS']['IPv4Groups']['Group']]
            elif isinstance(res['OMS']['IPv4Groups']['Group'], list):
                return res['OMS']['IPv4Groups']['Group']
        return []
    
    def get_ipv4_objs(self, name="", **kwargs):
        """获取IPv4对象"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4对象采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        res = self.netconf_get(data_xml)['top']

        if res:
            return res['OMS']['IPv4Objs']['Obj']
        else:
            return []
    
    def get_ipv4_paging(self, name="", map=True, **kwargs):
        """获取IPv4分页"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4分页信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        res = self.netconf_get(data_xml)
        
        type_map = {
            "0": "Nested group.",
            "1": "subnet",
            "2": "range",
            # "3": "Host address",
            "3": "ip",
            # "4": "Host name"
            "4": "HostName",
            "5": "User",
            "6": "UserGroup",
            "7": "Wildcard",
        }
        if res:
            if isinstance(res['top']['OMS']['IPv4Paging']['Group'], dict):
                res['top']['OMS']['IPv4Paging']['Group'] = [res['top']['OMS']['IPv4Paging']['Group']]
            for i in res['top']['OMS']['IPv4Paging']['Group']:
                if 'ObjList' in i.keys():
                    if isinstance(i['ObjList'], dict):
                        i['ObjList'] = [i['ObjList']]
                        if map:
                            for _t in i['ObjList']:
                                _t['Type'] = type_map[_t['Type']]
                    elif isinstance(i['ObjList'], list):
                        if map:
                            for _t in i['ObjList']:
                                _t['Type'] = type_map[_t['Type']]
            return res['top']['OMS']['IPv4Paging']['Group']
        else:
            return []
    
    def get_sec_zone(self, **kwargs):
        """获取安全区域"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全区域采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        execute_data = self.netconf_get(data_xml)
        return execute_data['top']['SecurityZone']['Zones']['Zone']
    
    def get_server_groups(self, name="", **kwargs):
        """获取服务器组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("服务器组采集需要XML模板配置")
        
        if name:
            data_xml = xml_templates[0].xml_template.format(name=name)
            execute_data = self.netconf_get(data_xml)
        else:
            data_xml = xml_templates[1].xml_template
            execute_data = self.netconf_get(data_xml)
        
        res = execute_data['top']
        if res:
            service_set = []
            groups = []
            service_result = dict()
            # 系统内置服务组
            if 'SysServGroups' in res['OMS'].keys():
                groups += res['OMS']['SysServGroups']['Group']
            # 用户定义服务组
            if 'ServGroups' in res['OMS'].keys():
                if isinstance(res['OMS']['ServGroups']['Group'], dict):
                    groups += [res['OMS']['ServGroups']['Group']]
                elif isinstance(res['OMS']['ServGroups']['Group'], list):
                    groups += res['OMS']['ServGroups']['Group']
            for i in groups:
                service_result[i['Name']] = i
            serv_objs = res['OMS']['ServObjs']['Obj']
            for i in serv_objs:
                if i['Group'] in service_result.keys():
                    if service_result[i['Group']].get('items'):
                        service_result[i['Group']]['items'].append(i)
                    else:
                        service_result[i['Group']]['items'] = [i]
            for i in service_result.keys():
                service_set.append(service_result[i])
            return service_set

        return []
    
    def get_ipv4_routes(self, **kwargs):
        """获取IPv4路由"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4路由采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        ifmgrlist = res['Ifmgr']['Interfaces']['Interface']
        routelist = res['Route']['Ipv4Routes']['RouteEntry']
        for a in routelist:
            for b in ifmgrlist:
                if 'IfIndex' in a.keys():
                    if a['IfIndex'] == b['IfIndex']:
                        a.update(Name=b['Name'])
        return routelist


class H3CSecPathDB(H3CNetconf):
    """基于数据库的H3C安全路径类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = 'H3C'
        self.device_type = kwargs.get('device_type', 'firewall')

    @staticmethod
    def get_method():
        """获取支持的方法列表"""
        return [
            'get_boards',
            'get_secpath_physical',
            'get_ipv4_oms',
            'get_ipv4_paging',
            'get_nataddr_group',
            'get_server_groups',
            'delete_sec_policy',
            'config_ipv4_rule',
            'edit_ipv4_rule',
            'config_sec_policy',
            'get_sec_policy_name',
            'get_sec_policy',
            'move_ipv4_rule',
            'get_sec_zone',
            'get_ipv4_addr',
            'query_server_groups',
            'get_sec_policy_id',
            'get_server_on_policy',
            'get_service_objs',
            'get_ipv4_group',
            'create_ipv4_group',
            'delete_ipv4_group',
            'delete_server_groups',
            'config_oms_objs',
            'create_service_groups',
            'get_oms_objs',
            'get_ipv4_objs',
            'get_ipv4_obj_data',
            'get_nat_server',
            'get_nat_addr_groups',
            'get_source_nat',
            'get_global_nat_policy',
            'config_nat_server',
            'del_nat_server',
            'config_top',
            'action_top',
            'config_snat_test',
            'config_sec_policy_test'
        ]

    def get_boards(self, **kwargs):
        """获取板卡信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("板卡信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        req = self.netconf_get(data_xml)
        if req:
            return req["top"]['Device']['PhysicalEntities']['Entity']
        return []
    
    def get_secpath_physical(self, class_flag=3, **kwargs):
        """获取安全路径物理信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全路径物理信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(class_flag=class_flag)
        req = self.netconf_get(data_xml)
        if req:
            PhysicalEntities = req["top"]['Device']['PhysicalEntities']['Entity']
            return PhysicalEntities
        else:
            return False
    
    def get_ipv4_oms(self, name, **kwargs):
        """获取IPv4 OMS信息"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4 OMS信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        res = self.netconf_get(data_xml)
        return res['top']['OMS']['GetIPv4ObjData']['Obj']
    
    def get_ipv4_paging(self, name="", map=True, **kwargs):
        """获取IPv4分页"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4分页信息采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        res = self.netconf_get(data_xml)
        # type 0—Nested group.
        # • 1—Subnet.
        # • 2—Range.
        # • 3—Host address.
        # • 4—Host name.
        type_map = {
            "0": "Nested group.",
            "1": "subnet",
            "2": "range",
            # "3": "Host address",
            "3": "ip",
            # "4": "Host name"
            "4": "HostName",
            "5": "User",
            "6": "UserGroup",
            "7": "Wildcard",
        }
        if res:
            if isinstance(res['top']['OMS']['IPv4Paging']['Group'], dict):
                res['top']['OMS']['IPv4Paging']['Group'] = [res['top']['OMS']['IPv4Paging']['Group']]
            # step1 把object格式统一list类型
            for i in res['top']['OMS']['IPv4Paging']['Group']:
                if 'ObjList' in i.keys():
                    if isinstance(i['ObjList'], dict):
                        i['ObjList'] = [i['ObjList']]
            # step2 判断有没有因为page分页问题没有显示全的条目，如果有就继续补充
            for i in res['top']['OMS']['IPv4Paging']['Group']:
                if 'ObjList' in i.keys():
                    if len(i['ObjList']) != int(i['ObjNum']):
                        ext_items = self.get_ipv4_oms(name=i['Name'])
                        if ext_items:
                            i['ObjList'] += ext_items
            # step3 格式化type
            for i in res['top']['OMS']['IPv4Paging']['Group']:
                if 'ObjList' in i.keys():
                    if map:
                        for _t in i['ObjList']:
                            _t['Type'] = type_map[_t['Type']]
            return res['top']['OMS']['IPv4Paging']['Group']
        else:
            return []
    
    def get_nataddr_group(self, **kwargs):
        """获取NAT地址组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)
        if res:
            addr_groups = res["top"]["NAT"]['AddrGroups']['AddrGroup']
            addr_group_members = res["top"]["NAT"]['AddrGroupMembers']['GroupMember']
            if isinstance(addr_groups, dict):
                addr_groups = [addr_groups]
            if isinstance(addr_group_members, dict):
                addr_group_members = [addr_group_members]
            for a in addr_groups:
                for b in addr_group_members:
                    if a['GroupNumber'] == b['GroupNumber']:
                        a.update(b)
            return addr_groups
        else:
            return []
    
    def get_server_groups(self, name="", **kwargs):
        """获取服务器组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        

        if name:
            data_xml = xml_templates[0].xml_template.format(name=name)
        else:
            data_xml = xml_templates[1].xml_template
        
        res = self.netconf_get(data_xml)['top']
        if res:
            service_set = []
            groups = []
            service_result = dict()
            # 系统内置服务组
            if 'SysServGroups' in res['OMS'].keys():
                groups = res['OMS']['SysServGroups']['Group']
            # 用户定义服务组
            if 'ServGroups' in res['OMS'].keys():
                if isinstance(res['OMS']['ServGroups']['Group'], dict):
                    groups += [res['OMS']['ServGroups']['Group']]
                elif isinstance(res['OMS']['ServGroups']['Group'], list):
                    groups += res['OMS']['ServGroups']['Group']
            for i in groups:
                service_result[i['Name']] = i
            serv_objs = res['OMS']['ServObjs']['Obj']
            for i in serv_objs:
                if i['Group'] in service_result.keys():
                    if service_result[i['Group']].get('items'):
                        service_result[i['Group']]['items'].append(i)
                    else:
                        service_result[i['Group']]['items'] = [i]
            for i in service_result.keys():
                service_set.append(service_result[i])
            return service_set

        return []
        
    def delete_sec_policy(self, method, rule_id, **kwargs):
        """删除安全策略"""

        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(method=method, rule_id=rule_id)

        request_info = self.edit_config(xml_data=data_xml)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        return request_info, ''
    
    def config_ipv4_rule(self, **kwargs):
        """配置IPv4规则"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(**kwargs)

        request_info = self.edit_config(xml_data=data_xml)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        return request_info, ''
    
    def edit_ipv4_rule(self, **kwargs):
        """编辑IPv4规则"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(**kwargs)
        request_info = self.edit_config(xml_data=data_xml)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        return request_info, ''
    
    def config_sec_policy(self, SecurityPolicies):
        """配置安全策略"""
        dict_data = {
            'config':
                {
                    '@xmlns:xc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                    'top':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': 'merge',
                            'SecurityPolicies': SecurityPolicies['SecurityPolicies']
                        }
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        # print(data_xml)
        request_info = self.edit_config(xml_data=data_xml)
        # print(request_info)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        return request_info, ''
    
    def get_sec_policy_name(self, name, **kwargs):
        """获取安全策略名称"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)

        res = self.netconf_get(data_xml)['top']
        if 'SecurityPolicies' not in res.keys():
            return False
        if res:
            result = res['SecurityPolicies']['GetRules']['Rule']
            return result
        else:
            return False

    def get_sec_policy(self, **kwargs):
        """获取安全策略"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get_bulk(data_xml)['top']
        if 'SecurityPolicies' not in res.keys():
            return False
        if res:
            type_map = {'1': 'IPv4', '2': 'IPv6'}
            action_map = {'1': 'Deny', '2': 'Permit'}
            result = res['SecurityPolicies']['GetRules']['Rule']
            for i in result:
                i['Type'] = type_map[i['Type']]
                i['Action'] = action_map[i['Action']]
            return result
        else:
            return False
    
    def move_ipv4_rule(self, **kwargs):
        """移动IPv4规则"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")

        if kwargs.get('rule_id') and kwargs.get('target_id') and kwargs.get('insert'):
            if kwargs['insert'] == 'before':
                move_type = 2
            elif kwargs['insert'] == 'after':
                move_type = 3
            else:
                return False
            
            params = dict(id=kwargs['rule_id'], dest_id=kwargs['target_id'], move_type=move_type)       
            xml = xml_templates[0].xml_template.format(**params)
            request_info = self._action(xml)
            return request_info
        elif kwargs.get('rule_id') and kwargs.get('insert'):
            if kwargs['insert'] == 'first':
                move_type = '1'
            elif kwargs['insert'] == 'bottom':
                move_type = '4'
            else:
                return False
            params = dict(id=kwargs['rule_id'], move_type=move_type)
            xml = xml_templates[1].xml_template.format(**params)
            request_info = self._action(xml)
            return request_info
        return False
    
    def get_sec_zone(self, **kwargs):
        """获取安全区域"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        return res['SecurityZone']['Zones']['Zone']
    
    def get_ipv4_addr(self, **kwargs):
        """获取IPv4地址"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        if res:
            return dict(src=res['SecurityPolicies']['IPv4SrcAddr']['SrcAddr'],
                        dst=res['SecurityPolicies']['IPv4DestAddr']['DestAddr'])
        else:
            return []
    
    def query_server_groups(self, name, **kwargs):
        """查询服务器组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        
        res = self.netconf_get(data_xml)
        if res:
            return res['top']['OMS']['ServGroups']['Group']

        return []
    
    def get_sec_policy_id(self, rule_id, **kwargs):
        """获取安全策略ID"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(rule_id=rule_id)

        res = self.netconf_get(data_xml)['top']
        if 'SecurityPolicies' not in res.keys():
            return False
        if res:
            result = res['SecurityPolicies']['GetRules']['Rule']
            return result
        else:
            return False
    
    def get_server_on_policy(self, **kwargs):
        """获取策略上的服务器"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        
        res = self.netconf_get(data_xml)['top']
        if 'NAT' not in res.keys():
            return False
        if res:
            # 截取natinterface列表
            natinterface_res = res['NAT']['ServerOnInterfaces']['Interface']
            # 接口索引和name对应
            ifmgrlist = res['Ifmgr']['Interfaces']['Interface']
            if isinstance(natinterface_res, dict):
                natinterface_res = [natinterface_res]
            for a in natinterface_res:
                for b in ifmgrlist:
                    if a['IfIndex'] == b['IfIndex']:
                        a.update(Name=b['Name'])
            type_map = {
                '1': "icmp",
                '6': "tcp",
                '17': "udp",
            }
            return natinterface_res
        else:
            return False
    
    def get_service_objs(self, **kwargs):
        """获取服务对象"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        type_map = {
            "0": "Nested group",
            "1": "Protocol",
            "2": "ICMP",
            "3": "TCP",
            "4": "UDP",
            "5": "ICMPv6",
        }
        if res:
            for x in res['OMS']['ServObjs']['Obj']:
                x['Type'] = type_map[x['Type']]
            return res['OMS']['ServObjs']['Obj']
        else:
            return []
    
    def get_ipv4_group(self, **kwargs):
        """获取IPv4组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        res = self.netconf_get(data_xml)['top']
        if res:
            return res['OMS']['IPv4Groups']['Group']
        else:
            return []
    
    # 新建/修改地址组
    def create_ipv4_group(self, method="create", name="", description="", **kwargs):
        """创建IPv4组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        if not name:
            return False
        if description:
            data_xml = xml_templates[0].xml_template.format(method=method, name=name, description=description)
            request_info = self.edit_config(xml_data=data_xml)
            if isinstance(request_info, tuple):
                return request_info[0]
            return request_info
        else:
            data_xml = xml_templates[1].xml_template.format(method=method, name=name)
            request_info = self.edit_config(xml_data=data_xml)
            if isinstance(request_info, tuple):
                return request_info[0]
            return request_info

    def delete_ipv4_group(self, name, **kwargs):
        """删除IPv4组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)

        request_info = self.edit_config(xml_data=data_xml)
        if isinstance(request_info, tuple):
            return request_info[0]
        return request_info

    def delete_server_groups(self, name, **kwargs):
        """删除服务器组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)

        request_info = self.edit_config(xml_data=data_xml)
        if isinstance(request_info, tuple):
            return request_info[0]
        return request_info
    
    # 配置OMS对象
    def config_oms_objs(self, OMS, **kwargs):
        """
        这是修改地址组某一个条目案例
        <top xmlns='http://www.h3c.com/netconf/config:1.0' web:operation='replace'>
        <OMS>
        <IPv4Objs web:operation='remove'>
        <Obj>
        <Group>12.101测试</Group>
        <ID>10</ID>
        </Obj>
        </IPv4Objs>
        </OMS>
        <OMS>
        <IPv4Objs web:operation='create'>
        <Obj>
        <Group>12.101测试</Group>
        <ID>4294967295</ID>
        <Type>1</Type>
        <SubnetIPv4Address>1.1.1.1</SubnetIPv4Address>
        <IPv4Mask>255.255.255.255</IPv4Mask>
        </Obj>
        </IPv4Objs>
        </OMS>
        </top>
        # 这是新增条目 网段形式
        <top xmlns='http://www.h3c.com/netconf/config:1.0' web:operation='replace'>
        <OMS>
        <IPv4Objs web:operation='create'>
        <Obj>
        <Group>12.101测试</Group>
        <ID>4294967295</ID>
        <Type>1</Type>
        <SubnetIPv4Address>2.2.2.2</SubnetIPv4Address>
        <IPv4Mask>255.255.255.255</IPv4Mask>
        </Obj>
        </IPv4Objs>
        </OMS>
        </top>
        # 删除条目 range
        <top xmlns='http://www.h3c.com/netconf/config:1.0' web:operation='replace'>
        <OMS>
        <IPv4Objs web:operation='remove'>
        <Obj>
        <Group>12.101测试</Group>
        <ID>0</ID>
        </Obj>
        </IPv4Objs>
        </OMS>
        </top>
        # 新增条目 range
        <top xmlns='http://www.h3c.com/netconf/config:1.0' web:operation='replace'>
        <OMS>
        <IPv4Objs web:operation='create'>
        <Obj>
        <Group>12.101测试</Group>
        <ID>4294967295</ID>
        <Type>2</Type>
        <StartIPv4Address>3.3.3.1</StartIPv4Address>
        <EndIPv4Address>3.3.3.2</EndIPv4Address>
        </Obj>
        </IPv4Objs>
        </OMS>
        </top>
        :param OMS:
        :return:
        """
        dict_data = {
            'config':
                {
                    '@xmlns:xc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                    'top':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            'OMS': OMS
                        }
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        request_info = self.edit_config(xml_data=data_xml)
        # print(request_info)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        elif isinstance(request_info, bool):
            return request_info, ''
        return False, 'netconf未捕获到预期的返回结果'
    
    def create_service_groups(self, method="create", name="", description="", **kwargs):
        """创建服务组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("安全策略名称采集需要XML模板配置")
        
        if not name:
            return False
        if description:
            data_xml = xml_templates[0].xml_template.format(method=method, name=name, description=description)
            request_info = self.edit_config(xml_data=data_xml)
            if isinstance(request_info, tuple):
                return request_info[0]
            return request_info
        else:
            data_xml = xml_templates[1].xml_template.format(method=method, name=name)
            request_info = self.edit_config(xml_data=data_xml)
            if isinstance(request_info, tuple):
                return request_info[0]
            return request_info
    
    def get_oms_objs(self, OMS):
        dict_data = {
            'top':
                {
                    '@xmlns': 'http://www.h3c.com/netconf/data:1.0',
                    'OMS': OMS
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        res = self.netconf_get(data_xml)['top']
        if 'IPv4Objs' in res['OMS'].keys():
            if isinstance(res['OMS']['IPv4Objs']['Obj'], dict):
                res['OMS']['IPv4Objs']['Obj'] = [res['OMS']['IPv4Objs']['Obj']]
        if 'ServObjs' in res['OMS'].keys():
            if isinstance(res['OMS']['ServObjs']['Obj'], dict):
                res['OMS']['ServObjs']['Obj'] = [res['OMS']['ServObjs']['Obj']]
        return res['OMS']
    
    def get_ipv4_objs(self, **kwargs):
        """获取IPv4对象"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4对象采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(**kwargs)
        res = self.netconf_get(data_xml)['top']
        type_map = {
            "1": "subnet",
            "2": "range",
            # "3": "Host address",
            "3": "ip",
            # "4": "Host name"
            "4": "HostName"
        }
        if res:
            if isinstance(res['OMS']['IPv4Objs']['Obj'], dict):
                res['OMS']['IPv4Objs']['Obj'] = [res['OMS']['IPv4Objs']['Obj']]
            return res['OMS']['IPv4Objs']['Obj']
        else:
            return []
    
    def get_ipv4_obj_data(self, name='', **kwargs):
        """获取IPv4对象数据"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("IPv4对象数据采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template.format(name=name)
        
        res = self.netconf_get(data_xml)['top']
        if res:
            return res['OMS']['GetIPv4ObjData']['Obj']
        else:
            return []
        
    def get_nat_server(self, **kwargs):
        """获取NAT服务器"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT服务器采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        res = self.netconf_get(data_xml)['top']
        if res:
            return res['NAT']['ServerOnInterfaces']['Interface']
        return []
    
    def get_nat_addr_groups(self, **kwargs):
        """获取NAT地址组"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        req = self.netconf_get(data_xml)['top']
        if req:
            return req['NAT']
        return []

    def get_source_nat(self, **kwargs):
        """获取源NAT"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template

        action_map = {
            '0': 'NO-PAT',
            '1': 'PAT',
            '2': 'EasyIp',
            '3': 'NO NAT'
        }
        req = self.netconf_get(data_xml)['top']
        if req:
            if 'NAT' not in req.keys():
                return []
            ifmgr_list = req['Ifmgr']['Interfaces']['Interface']
            nat_res = req['NAT']['PolicyRuleMembers']['Rule']
            # 两个表格合并，将name加入arp表格
            if isinstance(nat_res, dict):
                nat_res = [nat_res]
            for a in nat_res:
                a['Action'] = action_map[a['Action']]
                for b in ifmgr_list:
                    if a['OutboundInterface'] == b['IfIndex']:
                        a.update(OutboundInterfaceName=b['Name'])
            return nat_res
        return []
    
    def get_global_nat_policy(self, mode='DNAT', name='', **kwargs):
        """获取全局NAT策略"""
        """
        10.254.12.100 不支持 <TransSrcIP/>  (在Rule下)
        :param mode:
        :return:
        """
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        print('get_global_nat_policy mode:', self.netconf_dict['device_params']['name'])
        if self.netconf_dict['device_params']['name'] == "hpcomware":
            return []
        # 默认获取DNAT
        if mode == 'DNAT':
            TransMode = '1'  # DNAT
        else:
            TransMode = '0'  # SNAT
        if name != '':
            data_xml = xml_templates[0].xml_template.format(RuleName=name)
            res = self.netconf_get(data_xml)
        else:
            data_xml = xml_templates[1].xml_template.format(RuleName=name, TransMode=TransMode)
            res = self.netconf_get_bulk(data_xml)           

        if res:
            if 'NAT' in res['top'].keys():
                trans_mode_map = {
                    '0': 'SNAT',
                    '1': 'DNAT',
                }
                if name != '':
                    results = res['top']['NAT']
                else:
                    results = res['top']['NAT']['GlobalPolicyRuleMembers']['Rule']
                if isinstance(results, dict):
                    return [results]
                return results
        return []
    
    # 配置DNAT
    def config_nat_server(self, NAT: list, method='create'):
        dict_data = {
            'config':
                {
                    '@xmlns:xc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                    'top':
                        {
                            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                            '@xc:operation': method if method else 'create',
                            'NAT': NAT
                        }
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        logger.debug(f"配置TOP XML: {data_xml}")
        request_info = self.edit_config(xml_data=data_xml)

        if isinstance(request_info, tuple):
            return request_info[0]
        return request_info

    # DELETE NAT
    def del_nat_server(self, RuleName):
        dict_data = {
            'top': {
                '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
                '@xc:operation': 'remove',
                'NAT': {
                    'GlobalPolicyRules': {
                        'Rule': [{'RuleName': RuleName}]
                    }
                }
            }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        request_info = self.edit_config(xml_data=data_xml)
        # print(request_info)
        if isinstance(request_info, tuple):
            return request_info[0]
        return request_info
    
    # top通用配置
    def config_top(self, top):
        dict_data = {
            'config':
                {
                    '@xmlns:xc': 'urn:ietf:params:xml:ns:netconf:base:1.0',
                    'top': top
                }
        }
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        logger.debug(f"配置TOP XML: {data_xml}")
        request_info = self.edit_config(xml_data=data_xml)
        # print(request_info)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        elif isinstance(request_info, bool):
            return request_info, ''
        return False, 'netconf未捕获到预期的返回结果'
    
    def action_top(self, top):
        """
        {'top': {
        '@xmlns': 'http://www.h3c.com/netconf/action:1.0',
        'SecurityPolicies':
        {'MoveIPv4Rule': {'Rule': {'ID': '{id}', 'MoveType': '{move_type}'}}}}}
        :param dict_data:
        :return:
        """
        dict_data = {'top': top}
        res = XmlToDict().dicttoxml(dict=dict_data)
        data_xml = res.split('\n')[1]
        request_info = self._action(data=data_xml)
        # print(request_info)
        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        elif isinstance(request_info, bool):
            return request_info, ''
        return False, 'netconf未捕获到预期的返回结果'
    
    def config_snat_test(self, **kwargs):
        """配置SNAT测试"""
        xml_templates = kwargs.get('xml_templates', [])
        if not xml_templates:
            raise ValueError("NAT地址组采集需要XML模板配置")
        
        data_xml = xml_templates[0].xml_template
        request_info = self.edit_config(xml_data=data_xml)

        if isinstance(request_info, tuple):
            return request_info[0], request_info[1]
        elif isinstance(request_info, bool):
            return request_info, ''
        return False, 'netconf未捕获到预期的返回结果'
    
    def config_sec_policy_test(self):
        IPv4Rules = {
            'IPv4Rules':
                {
                    'Rule': {
                        'ID': 65535,
                        'RuleName': 'test123456',
                        'Action': 2,
                        'Enable': False,
                        'Log': False,
                        'Counting': False,
                        'SessAgingTimeSw': False,
                        'SessPersistAgingTimeSw': False,
                    }
                }
        }
        config_data = [

        ]
        data = [{
            '@xmlns': 'http://www.h3c.com/netconf/config:1.0',
            '@xc:operation': 'create',
            'SecurityPolicies': IPv4Rules
        }]
        return self.config_top(top=data)