import re
import math
from .base import register_processor


def mathintspeed(value):
    """接口speed单位换算"""
    k = 1000
    try:
        value = int(value) * 1000000
    except:
        return value
    if value == 0:
        return str(value)
    # value = value * 8
    sizes = ['bytes', 'K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y']
    c = math.floor(math.log(value) / math.log(k))
    value = (value / math.pow(k, c))
    value = '% 6.0f' % value
    value = str(value) + sizes[c]
    return value.strip()


def h3c_speed_format(interface):
    if re.search(r'^(GE)', interface) or re.search(
            r'^(GigabitEthernet)', interface):
        return '1G'

    elif re.search(r'^(XGE)', interface) or re.search(r'^(Ten-GigabitEthernet)', interface):
        return '10G'

    elif re.search(r'^(FGE)', interface) or re.search(r'^(FortyGigE)', interface):
        return '40G'

    elif re.search(r'^(Twenty-FiveGigE)', interface):
        return '25G'

    elif re.search(r'^(TwentyGigE)', interface):
        return '20G'

    elif re.search(r'^(TwoHundredGigE)', interface):
        return '200G'

    elif re.search(r'^(FourHundredGigE)', interface):
        return '400G'

    elif re.search(r'^(HGE)', interface):
        return '100G'

    elif re.search(r'^(MGE)', interface) or re.search(r'^(MEth)', interface):
        return '1G'

    elif re.search(r'^(M-GE)', interface):
        return '1G'
    return interface


@register_processor(vendor='H3C', device_type='交换机', collection_type='interface_brief', method='netconf')
def process_interface_brief_netconf(data):
    """H3C 交换机 ARP 处理 (NETCONF)"""
    data = data['data']['top']['Ifmgr']['Interfaces']['Interface']
    layer2datas = []
    for i in data:
        # 正常物理接口都会带speed和duplex的key，不带则是逻辑接口
        if 'ActualSpeed' in i.keys() and 'ActualDuplex' in i.keys():
            if i['Name'].startswith('M-'):
                continue
            elif i['Name'].startswith('Bridge-Aggregation'):
                continue
            elif i['Name'].startswith('Vlan-interface'):
                continue
            elif i['Name'].startswith('InLoopBack'):
                continue
            elif i['Name'].startswith('NULL'):
                continue
            if i['ActualSpeed'] == '0':
                i['ActualSpeed'] = h3c_speed_format(
                    i['Name'])
            if mathintspeed(
                    i['ActualSpeed']) == '830G':
                i['ActualSpeed'] = h3c_speed_format(
                    i['Name'])
            layer2datas.append(dict(
                        interface=i['Name'],
                        status=i['OperStatus'],
                        speed=mathintspeed(
                            i['ActualSpeed']),
                        duplex=i['ActualDuplex'],
                        description=i['Description']))
    return layer2datas