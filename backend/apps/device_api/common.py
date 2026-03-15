import math
import re


device_type_map = {
    "H3C": "hp_comware",
    "Huawei": "huawei",
    "Hillstone": "hillstone",
    "Mellanox": "mellanox",
    "centec": "cisco_ios",
    "Ruijie": "ruijie_os",
    "Maipu": "mypower",
    "Cisco": "cisco_ios",
    "ZTE": "zte_zxros",
}


class InterfaceFormat(object):
    @staticmethod
    def huawei_interface_format(interface):
        if re.search(r"^(GE)", interface):
            return interface.replace("GE", "GigabitEthernet")
        if re.search(r"^(XGE)", interface):
            return interface.replace("XGE", "XGigabitEthernet")
        return interface

    @staticmethod
    def h3c_interface_format(interface):
        if re.search(r"^(GE)", interface):
            return interface.replace("GE", "GigabitEthernet")
        if re.search(r"^(BAGG)", interface):
            return interface.replace("BAGG", "Bridge-Aggregation")
        if re.search(r"^(RAGG)", interface):
            return interface.replace("RAGG", "Route-Aggregation")
        if re.search(r"^(XGE)", interface):
            return interface.replace("XGE", "Ten-GigabitEthernet")
        if re.search(r"^(TGE)", interface):
            return interface.replace("TGE", "TwentyGigE")
        if re.search(r"^(HGE)", interface):
            return interface.replace("HGE", "HundredGigE")
        if re.search(r"^(FGE)", interface):
            return interface.replace("FGE", "FortyGigE")
        if re.search(r"^(MGE)", interface):
            return interface.replace("MGE", "M-GigabitEthernet")
        if re.search(r"^(M-GE)", interface):
            return interface.replace("M-GE", "M-GigabitEtherne")
        return interface

    @staticmethod
    def maipu_interface_format(interface):
        if re.search(r"^(te)", interface):
            return interface.replace("te", "tengigabitethernet")
        return interface

    @staticmethod
    def ruijie_speed_format(interface):
        if re.search(r"^(GigabitEthernet)", interface):
            return "1G"
        if re.search(r"^(TenGigabitEthernet)", interface):
            return "10G"
        if re.search(r"^(TFGigabitEthernet)", interface):
            return "10G"
        if re.search(r"^(FortyGigabitEthernet)", interface):
            return "40G"
        if re.search(r"^(HundredGigabitEthernet)", interface):
            return "100G"
        return interface

    @staticmethod
    def cisco_speed_format(interface):
        if re.search(r"^(GigabitEthernet)", interface):
            return "1G"
        if re.search(r"^(TenGigabitEthernet)", interface):
            return "10G"
        if re.search(r"^(TFGigabitEthernet)", interface):
            return "10G"
        if re.search(r"^(FortyGigabitEthernet)", interface):
            return "40G"
        if re.search(r"^(HundredGigabitEthernet)", interface):
            return "100G"
        return interface

    @staticmethod
    def mathintspeed(value):
        k = 1000
        try:
            value = int(value) * 1000000
        except Exception:
            return value
        if value == 0:
            return str(value)
        sizes = ["bytes", "K", "M", "G", "T", "P", "E", "Z", "Y"]
        c = math.floor(math.log(value) / math.log(k))
        value = value / math.pow(k, c)
        value = "% 6.0f" % value
        value = str(value) + sizes[c]
        return value.strip()
