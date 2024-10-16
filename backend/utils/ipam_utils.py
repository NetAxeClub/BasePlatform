# IPAM接口输出到运营平台
from apps.open_ipam.models import Subnet
from netaddr import IPNetwork, IPSet


class IpAmForNetwork(object):

    # 根据给定的一系列子网信息，自动生成树
    def generate_tree(self, some_subnets):
        '''
        :param some_subnets: 一系列子网信息
        :return: 一个4层树结构
        '''
        res_list = some_subnets
        res_list_cp = res_list.copy()
        # print(res_list)
        no1_id_list = []  # 存放第一层子网的ipam_id
        no1_list = []  # 存放第一层子网的详细信息
        no2_id_list = []
        no2_list = []
        no3_id_list = []
        no3_list = []
        no4_id_list = []
        no4_list = []
        for i in res_list:
            if i['masterSubnetId'] == 0:
                no1_id_list.append(i['ipam_id'])
                tmp = {}
                tmp['id'] = i['ipam_id']
                tmp['masterSubnetId'] = i['masterSubnetId']
                tmp['label'] = i['ipName']
                tmp['children'] = []
                no1_list.append(tmp)
                res_list_cp.remove(i)

        # print(len(no1_id_list), len(res_list_cp))

        for i in res_list:
            if i['masterSubnetId'] in no1_id_list:
                no2_id_list.append(i['ipam_id'])
                tmp = {}
                tmp['id'] = i['ipam_id']
                tmp['masterSubnetId'] = i['masterSubnetId']
                tmp['label'] = i['ipName']
                tmp['children'] = []
                no2_list.append(tmp)
                res_list_cp.remove(i)

        print(len(no2_id_list), len(res_list_cp))

        for i in res_list:
            if i['masterSubnetId'] in no2_id_list:
                no3_id_list.append(i['ipam_id'])
                tmp = {}
                tmp['id'] = i['ipam_id']
                tmp['masterSubnetId'] = i['masterSubnetId']
                tmp['label'] = i['ipName']
                tmp['children'] = []
                no3_list.append(tmp)
                res_list_cp.remove(i)

        print(len(no3_id_list), len(res_list_cp))

        for i in res_list:
            if i['masterSubnetId'] in no3_id_list:
                no4_id_list.append(i['ipam_id'])
                tmp = {}
                tmp['id'] = i['ipam_id']
                tmp['masterSubnetId'] = i['masterSubnetId']
                tmp['label'] = i['ipName']
                tmp['children'] = []
                no4_list.append(tmp)
                res_list_cp.remove(i)

        print(len(no4_id_list), len(res_list_cp))

        for i in no3_list:
            for j in no4_list:
                if j["masterSubnetId"] == i["id"]:
                    i['children'].append(j)

        for i in no2_list:
            for j in no3_list:
                if j["masterSubnetId"] == i["id"]:
                    i['children'].append(j)

        for i in no1_list:
            for j in no2_list:
                if j["masterSubnetId"] == i["id"]:
                    i['children'].append(j)

        # no1_list = sorted(no1_list, key=lambda e: e['id'], reverse=False)

        return no1_list

    def generate_netops_tree(self, some_subnets):
        print("some_subnets",some_subnets)
        '''
        :param some_subnets: 一系列子网信息
        :return: 一个5层树结构
        '''
        res_list = some_subnets
        # res_list_cp = res_list.copy()
        # subnet_dict = {}  # 存放每个子网的详细信息
        # root_subnets = []  # 存放根子网

        res_list = some_subnets
        subnet_dict = {}  # 存放每个子网的详细信息
        root_subnets = []  # 存放根子网

        # 首先，遍历所有子网，构建字典和根子网列表
        for e in res_list:
            subnet_dict[e['id']] = {
                'id': e['id'],
                'master_subnet_id': e['master_subnet_id'],
                'network_type': e['network_type'],
                'label': str(e['subnet']),
                'children': []
            }
            if e['master_subnet_id'] is None:
                root_subnets.append(e['id'])

        # 然后，遍历字典，将子网添加到它们的父级
        for subnet_id, details in subnet_dict.items():
            if details['master_subnet_id'] is not None:
                parent_subnet_id = details['master_subnet_id']
                if parent_subnet_id in subnet_dict:
                    subnet_dict[parent_subnet_id]['children'].append(details)

        # 最后返回根子网列表
        return [subnet_dict[root_subnet] for root_subnet in root_subnets]

    # 根据给定的一系列子网信息，自动生成树-2022.05.31 TODO:结果是dict结构
    def build_tree_recursive(self, node_list, parent=None):
        '''
        :param node_list: all_subnets = list(IpamSubnet.objects.all().values('ipam_id', 'master_subnet_id', 'ipName'))
        :param parent: {'ipam_id': 0, 'master_subnet_id': None, 'ipName': '0.0.0.0/0'}
        :return:
        '''
        if not parent:
            parent = {'ipam_id': 0, 'master_subnet_id': None, 'ipName': '0.0.0.0/0'}
        children = []
        for i in node_list:
            if i.get('master_subnet_id') == parent['ipam_id']:
                children.append(i)

        parent['children'] = children

        for j in children:
            self.build_tree_recursive(node_list, parent=j)

        return parent

    #  返回树结构，所有子网
    def ipam_tree_all(self):
        # 获取总数
        all_subnets = Subnet.objects.all().values('id', 'master_subnet_id', 'name')
        res_list = list(all_subnets)
        res_list = [dict(t) for t in set([tuple(d.items()) for d in res_list])]
        res_list = sorted(res_list, key=lambda e: e['id'], reverse=False)

        tree = self.generate_tree(res_list)

        return tree

    #  # 为叶子节点，生成树结构
    def leaf_tree(self, leaf_node, all_subnets):
        res = [leaf_node]
        while leaf_node['master_subnet_id'] > 0:
            for i in all_subnets:
                if i['ipam_id'] == leaf_node['master_subnet_id']:
                    leaf_node = i
                    # print(leaf_node)
                    # res.append(leaf_node)
                    res.insert(0, leaf_node)
            else:
                break

        return res

    #  返回树结构,基于指定BGBU
    def ipam_tree_by_bgbu(self, bgbu_id):
        '''
        :param bgbu_id: [2,4,6,14]这样的列表信息
        '''
        pass

    def ipam_tree(self, bgbu=None):
        '''
        :param bgbu_id: [2,4,6,14]这样的列表信息
        '''
        if bgbu:
            tree = self.ipam_tree_by_bgbu(bgbu)
        else:
            tree = self.ipam_tree_all()

        return tree

    def get_sixteen_subnet_id(ip):
        # 排除ipv6地址同步操作
        if ":" not in ip:
            try:
                ip_mask = "{}/{}".format(ip, 16)
                subnet = "{}/{}".format(IPNetwork(ip_mask).network, 16)
                res = Subnet.objects.filter(subnet=subnet).values().first()
                if res:
                    return res['id']
            except Exception as e:
                return
        else:
            return
