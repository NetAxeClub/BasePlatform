# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      get_mongo_log
   Description:
   Author:          Administrator
   date：           2018/6/3
-------------------------------------------------
   Change Activity:
                    2018/6/3:
-------------------------------------------------
"""
import json
import re
from datetime import date, datetime, timedelta
import pymongo
from bson.objectid import ObjectId
from netaddr import IPAddress
from confload.confload import config


class JSONEncoder(json.JSONEncoder):
    """
    用于JSON序列化mongodb中的_id和date对象以及datetime对象
    """

    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        elif isinstance(o, datetime):
            return o.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(o, date):
            return o.strftime('%Y-%m-%d')
        return json.JSONEncoder.default(self, o)


def get_mongo_json_res(data):
    """
    用于将mongo数据进行JSON序列化
    :param data: mongo数据
    :return: JSON数据
    """
    res = JSONEncoder().encode(data)
    return res


mongo_client = pymongo.MongoClient(
    host=config.mongodb_host,
    port=config.mongodb_port,
    username=config.mongodb_user,
    password=config.mongodb_password,
    maxPoolSize=1000,
    connect=False)


# 4.3.3 pymongo版本弃用了Collection.remove is removed
# Removed pymongo.collection.Collection.remove(). Use delete_one() to delete a single document or delete_many() to delete multiple documents.
class MongoOps:
    def __init__(self, db, coll):
        self.db = mongo_client[db]
        self.coll = self.db[coll]

    def remove_collection_content(self):
        """
        清空集合中的内容
        :return:
        """
        self.coll.delete_many({})

    def close_client(self):
        return mongo_client.close()

    def all_table(self):
        return self.db.collection_names()

    def create_index(self, keys, session=None, **kwargs):
        # pymongo.ASCENDING 升序 从小到大
        # pymongo.DESCENDING 降序 从大到小
        """
        my_mongo = MongoOps(db='netops', coll='XunMi')
        my_mongo.create_index([("log_time", pymongo.DESCENDING)])
        my_mongo.create_index("server_ip_address")
        :param keys:
        :param session:
        :param kwargs:
        :return:
        """
        return self.coll.create_index(keys, session=session, **kwargs)

    def list_indexes(self):
        return self.coll.list_indexes()

    def drop_indexes(self):
        return self.coll.drop_indexes()

    def rebuild_index(self, session=None, **kwargs):
        return self.coll.reindex(session=None, **kwargs)

    def drop_index(self, index_or_name, session=None, **kwargs):
        return self.coll.drop_index(index_or_name, session=session, **kwargs)

    def insert_one(self, content):
        """
        将日志写入mongodb(新方法)建议方法合并到insert
        :type content: dict
        :return:
        """
        return self.coll.insert_one(content)

    def insert(self, content):
        """
        :type content: dict
        :return:
        """
        self.coll.insert_one(content)
        return

    def update(self, filter, update):
        """
        将日志写入mongodb
        :type content: dict
        :return:
        result = db.test.update_one({'x': 1}, {'$inc': {'x': 3}})
        res = my_mongo.update(filter=tmp[-1], update={"$set": {'start': int(tmp[-1]['start'])})
        """
        # self.coll.update_one(filter=filter, update=update)
        self.coll.update_many(filter=filter, update=update)
        return

    def update_one(self, filter, update):
        """
        将日志写入mongodb
        :type content: dict
        :return:
        result = db.test.update_one({'x': 1}, {'$inc': {'x': 3}})
        res = my_mongo.update(filter=tmp[-1], update={"$set": {'start': int(tmp[-1]['start']) + 10}})
        """
        result = self.coll.update_one(filter=filter, update=update)
        return result

    def find(self, query_dict=None, fileds=None, sort=None):
        """
        获取所有日志记录
        :param sort:
        :param fileds:
        :param query_dict: 字典形式，比如：{"name": "xxx"}
        example: fileds={'_id': 0, 'node_ip': 1}  只显示node_ip  指定字段
        :type query_dict: dict
        :return: 所有日志记录
        :rtype: list
        """
        if fileds and sort:
            r = self.coll.find(query_dict, fileds).sort(sort, 1)
        elif fileds:
            r = self.coll.find(query_dict, fileds)
        elif query_dict:
            r = self.coll.find(query_dict)
        else:
            r = self.coll.find()
        return list(r)

    def find_page_query(self, query_dict=None, fileds=None, sort=None, page_size=10, page_num=1):
        """
                获取所有日志记录
                :param sort:
                :param fileds:
                :param query_dict: 字典形式，比如：{"name": "xxx"}
                example: fileds={'_id': 0, 'node_ip': 1}  只显示node_ip  指定字段
                :type query_dict: dict
                :return: 所有日志记录
                :rtype: list
                """
        skip = page_size * (page_num)
        # 字段排序// -1 为倒序，1 为正序
        if fileds and sort:
            r = self.coll.find(query_dict, fileds).sort(sort, -1).limit(page_size).skip(skip)
        elif fileds:
            r = self.coll.find(query_dict, fileds).limit(page_size).skip(skip)
        elif query_dict:
            r = self.coll.find(query_dict).limit(page_size).skip(skip)
        else:
            r = self.coll.find().limit(page_size).skip(skip)
        return list(r)

    def find_re(self, kwargs, fileds=None, sort=None):
        """
        正则匹配  kwargs :{'name': re.compile(e)}
        example: fileds={'_id': 0, 'node_ip': 1}  只显示node_ip
        :return: 所有日志记录
        :rtype: list
        """
        if fileds and sort:
            r = self.coll.find(kwargs, fileds).sort(sort, 1)
        elif fileds:
            r = self.coll.find(kwargs, fileds)
        else:
            r = self.coll.find(kwargs)
        return list(r)

    def delete_single(self, query):
        """
        删除指定日志记录
        :return:
        """
        return self.coll.delete_one(query)

    def delete_one(self, spec_or_id):
        """
        删除指定日志记录
        :return:
        """
        return self.coll.remove(spec_or_id)

    def delete_many(self, query=None):
        """
        删除所有日志记录
        :return:
        """
        if query is None:
            return self.coll.delete_many({})
        return self.coll.delete_many(query)

    def delete(self, spec_or_id=None):
        """
        删除所有日志记录
        :return:
        """
        if spec_or_id:
            return self.coll.remove(spec_or_id=spec_or_id)
        else:
            return self.coll.delete_many({})

    def insert_many(self, doc):
        """
        批量插入操作,doc是一个list
        :return:
        """
        return self.coll.insert_many(documents=doc)

    def count_documents(self):
        """
        统计集合中的文档数
        :return:
        """
        return self.coll.count_documents({})

    def group_by(self, group_key):
        # groupby = group_key

        group = {
            '_id': "$%s" % (group_key if group_key else None),
            "part_quantity": {"$sum": 1}
        }

        ret = self.coll.aggregate(
            [
                {'$group': group},
            ]
        )
        # print(ret)
        return ret


xunmi_mongo = MongoOps(db='netops', coll='XunMi')
lagg_mongo = MongoOps(db='Automation', coll='AggreTable')
compliance_mongo = MongoOps(db='Automation', coll='ConfigCompliance')
topology_mongo = MongoOps(db='Automation', coll='topology')


class MongoNetOps(object):
    @staticmethod
    def del_topology(name):
        topology_mongo.delete_many(query={'name': name})
        return

    @staticmethod
    def get_topology(name):
        _query = topology_mongo.find(query_dict={'name': name}, fileds={'_id': 0})
        if _query:
            return _query[0]
        return []

    @staticmethod
    def topology_ops(**data):
        _query = topology_mongo.find(query_dict={'name': data['name']}, fileds={'_id': 0})
        if _query:
            topology_mongo.delete_many(query={'name': data['name']})
            topology_mongo.insert(data)
        else:
            topology_mongo.insert(data)
        return

    @staticmethod
    def compliance_result(**kwargs):
        res = compliance_mongo.find(query_dict=kwargs, fileds={'_id': 0})
        return res

    @staticmethod
    def post_cmdb(data):
        cmdb_mongo = MongoOps(db='Automation', coll='networkdevice')
        if len(data) > 0:
            cmdb_mongo.delete_many()
            cmdb_mongo.insert_many(data)
            cmdb_mongo.drop_indexes()
            cmdb_mongo.create_index([('manage_ip', pymongo.DESCENDING)])
            cmdb_mongo.create_index([('idc__name', pymongo.DESCENDING)])
        return

    @staticmethod
    def compliance_ops(**kwargs):
        log_time = kwargs['log_time']
        kwargs.pop('log_time')
        query_tmp = compliance_mongo.find(query_dict=kwargs)
        if query_tmp:
            if query_tmp[0]['log_time'] != log_time:
                compliance_mongo.update(filter=kwargs, update={"$set": {'log_time': log_time}})
                return 'update'
            else:
                return 'equal no ops', None  # return ('equal no ops', None) 相同无需操作
        else:
            kwargs['log_time'] = log_time
            compliance_mongo.insert(kwargs)
            return 'insert'

    @staticmethod
    def compliance_reindex():
        my_mongo = MongoOps(db='Automation', coll='ConfigCompliance')
        my_mongo.drop_indexes()
        my_mongo.create_index([('log_time', pymongo.DESCENDING)])
        my_mongo.create_index("hostip")
        my_mongo.create_index("vendor")
        return

    @staticmethod
    def arp_reindex():
        """
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='ARPTable')
        # my_mongo.list_indexes()
        # my_mongo.rebuild_index()
        my_mongo.drop_indexes()
        my_mongo.create_index([('log_time', pymongo.DESCENDING)])
        my_mongo.create_index("ipaddress")
        my_mongo.create_index("macaddress")
        my_mongo.create_index("hostip")
        return

    @staticmethod
    def macaddress_reindex():
        """
        :return:
        """
        my_mongo = MongoOps(db='Automation', coll='MACTable')
        # my_mongo.list_indexes()
        # my_mongo.rebuild_index()
        my_mongo.drop_indexes()
        my_mongo.create_index([('log_time', pymongo.DESCENDING)])
        my_mongo.create_index("macaddress")
        my_mongo.create_index("hostip")
        return

    # 查询山石防火墙服务组定义
    @staticmethod
    def hillstone_service_query(**kwargs):
        service_mongo = MongoOps(db='Automation', coll='hillstone_service')
        predefined_mongo = MongoOps(db='Automation', coll='hillstone_service_predefined')
        protocol = kwargs['protocol'].upper()
        start_port = kwargs['start_port']
        end_port = kwargs['end_port']
        hostip = kwargs['hostip']
        # 先查系统预定义服务
        predefined_res = predefined_mongo.find(query_dict={"protocol": protocol, "hostip": hostip,
                                                           "dstport_start": start_port,
                                                           "dstport_end": end_port}, fileds={'_id': 0})
        if predefined_res:
            return predefined_res[0]
        # 单个端口的情况下
        if start_port == end_port:
            service_res = service_mongo.find(query_dict={"hostip": hostip,
                                                         'items': {
                                                             '$elemMatch': {
                                                                 'dst-port-min': start_port,
                                                                 'protocol': protocol.lower()
                                                             }
                                                         }}, fileds={'_id': 0})
            if service_res:
                return service_res[0]
        else:
            service_res = service_mongo.find(query_dict={"hostip": hostip,
                                                         'items': {
                                                             '$elemMatch': {
                                                                 'dst-port-min': start_port,
                                                                 'dst-port-max': end_port,
                                                                 'protocol': protocol.lower()
                                                             }
                                                         }}, fileds={'_id': 0})
            if service_res:
                return service_res[0]

        return []

    # 查询华三防火墙服务定义
    @staticmethod
    def h3c_service_query(**kwargs):
        # TCP 3 UDP 4 ICMP 2
        protocol_map = {
            'TCP': '3',
            'UDP': '4',
            'ICMP': '2',
        }
        service_mongo = MongoOps(db='NETCONF', coll='h3c_service_set')
        protocol = kwargs['protocol'].upper()
        start_port = kwargs['start_port']
        end_port = kwargs['end_port']
        hostip = kwargs['hostip']
        service_res = service_mongo.find(query_dict={"hostip": hostip,
                                                     'items': {
                                                         '$elemMatch': {
                                                             'Type': protocol_map[protocol],
                                                             'StartDestPort': str(start_port),
                                                             'EndDestPort': str(end_port),
                                                             'StartSrcPort': '1',
                                                             'EndSrcPort': '65535'
                                                         }
                                                     }}, fileds={'_id': 0})
        if service_res:
            return service_res[0]

    # 安全纳管-查询地址组中包含的地址
    @staticmethod
    def addr_map(**kwargs):
        ipaddress = kwargs['ip']
        vendor = kwargs.get('vendor')
        hostip = kwargs.get('hostip')
        my_mongo = MongoOps(db='Automation', coll='hillstone_address')
        res = my_mongo.find_re({"ip.ip": {"$regex": ipaddress}}, fileds={'_id': 0})
        my_mongo.close_client()
        return res

    # 安全纳管-查询公网IP归属出口设备
    @staticmethod
    def dnat_ip_owner_query(ip):
        _ip = IPAddress(ip)
        params = {
            'location': {'$elemMatch': {'start': {'$lte': _ip.value}, 'end': {'$gte': _ip.value}}}}
        my_mongo = MongoOps(db='Automation', coll='layer3interface')
        res = my_mongo.find(query_dict=params, fileds={'_id': 0})
        return list(set([x['hostip'] for x in res])) if res else []

    # 查询dnat归属
    @staticmethod
    def dnat_query(hostip, ip, port, type):
        if type == 'global_ip':
            if hostip and port and ip:
                _ip = IPAddress(ip)
                params = {
                    '$and': [
                        {
                            'global_ip': {
                                '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}
                        },
                        {
                            'global_port': {'$elemMatch': {'start': {'$lte': int(port)}, 'end': {'$gte': int(port)}}}
                        },
                        {
                            'hostip': hostip
                        }
                    ]
                }
            elif ip and hostip:
                _ip = IPAddress(ip)
                params = {
                    '$and': [
                        {
                            'global_ip': {
                                '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}
                        },
                        {
                            'hostip': hostip
                        }
                    ]
                }
            elif ip and port:
                _ip = IPAddress(ip)
                params = {
                    '$and': [{'global_ip': {
                        '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}},
                        {'global_port': {'$elemMatch': {'start': {'$lte': int(port)}, 'end': {'$gte': int(port)}}}}
                    ]}
            elif hostip:
                params = {'hostip': hostip}
            elif ip:
                _ip = IPAddress(ip)
                params = {
                    'global_ip': {'$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}}
            else:
                _ip = IPAddress(ip)
                params = {
                    'global_ip': {'$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}}
        else:
            if hostip and port and ip:
                _ip = IPAddress(ip)
                params = {
                    '$and': [
                        {
                            'local_ip': {
                                '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}
                        },
                        {
                            'local_port': {'$elemMatch': {'start': {'$lte': int(port)}, 'end': {'$gte': int(port)}}}
                        },
                        {
                            'hostip': hostip
                        }
                    ]}
            elif ip and hostip:
                _ip = IPAddress(ip)
                params = {
                    '$and': [
                        {
                            'local_ip': {
                                '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}
                        },
                        {
                            'hostip': hostip
                        }
                    ]}
            elif ip and port:
                _ip = IPAddress(ip)
                params = {
                    '$and': [{'local_ip': {
                        '$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}},
                        {'local_port': {'$elemMatch': {'start': {'$lte': int(port)}, 'end': {'$gte': int(port)}}}}
                    ]}
            elif hostip:
                params = {'hostip': hostip}
            elif ip:
                _ip = IPAddress(ip)
                params = {
                    'local_ip': {'$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}}
            else:
                _ip = IPAddress(ip)
                params = {
                    'local_ip': {'$elemMatch': {'start_int': {'$lte': _ip.value}, 'end_int': {'$gte': _ip.value}}}}
        my_mongo = MongoOps(db='Automation', coll='DNAT')
        res_info = my_mongo.find(query_dict=params, fileds={'_id': 0})
        return res_info

    @staticmethod
    def getday(num):
        if isinstance(num, int):
            today = date.today()
            oneday = timedelta(days=num)
            yesterday = today - oneday
            return str(yesterday)
        else:
            return False

    @staticmethod
    def clear_xunmi():
        my_mongo = MongoOps(db='netops', coll='XunMi')
        # a = my_mongo.count_documents()
        today = date.today()
        oneday = timedelta(days=30)
        yesterday = today - oneday
        yesterday = datetime.strptime(str(yesterday), '%Y-%m-%d')
        a = my_mongo.delete_many({"log_time": {"$lte": yesterday}})
        return a

    @staticmethod
    def clear_interface_error():
        my_mongo = MongoOps(db='alarm', coll='interface_error')
        today = date.today()
        oneday = timedelta(days=15)
        yesterday = today - oneday
        yesterday = yesterday.strftime("%Y.%m.%d")
        my_mongo.delete_many(query={'time': re.compile(yesterday)})
        return

    @staticmethod
    def get_lldp_info(data: dict) -> list:
        """
        获取指定LLDP信息
        :param data:
        :param ipaddress:
        :return:
        """
        lldp_mongo = MongoOps(db='Automation', coll='LLDPTable')
        query_tmp = lldp_mongo.find(query_dict=data, fileds={'_id': 0})
        if query_tmp:
            return query_tmp if isinstance(query_tmp, list) else []
        else:
            return []

    @staticmethod
    def get_xunmi_info(data: dict) -> list:
        """
        获取指定寻觅信息
        :param data:
        :param ipaddress:
        :return:
        """
        my_mongo = MongoOps(db='netops', coll='XunMi')
        query_tmp = my_mongo.find(query_dict=data, fileds={'_id': 0}, sort='log_time')
        if query_tmp:
            data['log_time'] = query_tmp[-1]['log_time']
            res = my_mongo.find(query_dict=data, fileds={'_id': 0}, sort='log_time')
            return res if isinstance(res, list) else []
        else:
            return []

    @staticmethod
    def get_ip_info(ipaddress):
        """
        主要给讯飞云吴頔使用，引用在projs app的view中
        :param ipaddress:
        :return:
        """
        my_mongo = MongoOps(db='netops', coll='XunMi')
        mongo_data = dict(server_ip_address=ipaddress)
        tmp = my_mongo.find(query_dict=mongo_data, fileds={'_id': 0}, sort='log_time')
        if tmp:
            mongo_data['log_time'] = tmp[-1]['log_time']
            res = my_mongo.find(query_dict=mongo_data, fileds={'_id': 0}, sort='log_time')
            if res:
                for i in res:
                    # print(i)
                    i['log_time'] = i['log_time'].strftime("%Y-%m-%d %H:%M:%S")
                return res if isinstance(res, list) else False

        return False

    # 插入总表项集合
    @staticmethod
    def insert_table(db, hostip, datas, tablename, delete=True):
        # db='Automation',
        my_mongo = MongoOps(db=db, coll=tablename)
        if delete:
            my_mongo.delete_many(query=dict(hostip=hostip))
        my_mongo.insert_many(datas)
        # netconf_mongo.insert_many(datas)
        return

    @staticmethod
    def failed_log(ip, fsm_flag, cmd, version):
        failed_mongo = MongoOps(db='Automation', coll='fsm_failed_logs')
        failed_mongo.insert(
            dict(
                ip=ip,
                fsm_flag=fsm_flag,
                cmd=cmd,
                version=version))


# IPAM操作集合
class IpamOps(object):
    def __init__(self):
        pass

    # 获取全网IP数据
    @staticmethod
    def get_total_ip():
        total_ip_mongo = MongoOps(db='Automation', coll='Total_ip_list')
        res = total_ip_mongo.find(fileds={'_id': 0})
        if res:
            return res
        else:
            return False

    # IPAM成功IP单条数据落库专用
    @staticmethod
    def post_success_ip(ip):
        """
        1、查询除log_time字段外，是否有完全匹配，如果有就只更新log_time字段, 如果log_time字段一致，则不进行任何操作
        2、如果查询不到数据，则新增该字段
        """
        log_time = datetime.now().strftime("%Y-%m-%d")
        my_mongo = MongoOps(db='IPAMData', coll='netaxe_ipam_success_ip')
        query_tmp = my_mongo.find(query_dict={'success_ip': ip})
        # print(query_tmp)
        if query_tmp:
            if query_tmp[0]['log_time'] != log_time:
                return 'update', my_mongo.update(filter={'success_ip': ip}, update={"$set": {'log_time': log_time}})
            else:
                return 'equal no ops', None
        else:
            tmp = {}
            tmp['log_time'] = log_time
            tmp['success_ip'] = ip
            return 'insert', my_mongo.insert(tmp)

    # IPAM成功IP(list格式)批量写入
    @staticmethod
    def post_success_ip_bulk(success_ip_doc):
        format_doc = []
        for data in success_ip_doc:
            tmp = {}
            tmp['log_time'] = datetime.now().strftime("%Y-%m-%d")
            tmp['success_ip'] = data
            format_doc.append(tmp)

        my_mongo = MongoOps(db='IPAMData', coll='netaxe_ipam_success_ip')
        if len(format_doc) >= 1000:
            my_mongo.delete()
            my_mongo.insert_many(format_doc)
        doc_num = my_mongo.count_documents()

        return doc_num

    # IPAM失败IP单条数据落库专用
    @staticmethod
    def post_fail_ip(ip):
        """
        1、查询除log_time字段外，是否有完全匹配，如果有就只更新log_time字段, 如果log_time字段一致，则不进行任何操作
        2、如果查询不到数据，则新增该字段
        """
        log_time = datetime.now().strftime("%Y-%m-%d")
        my_mongo = MongoOps(db='IPAMData', coll='netaxe_ipam_fail_ip')
        query_tmp = my_mongo.find(query_dict={'fail_ip': ip})
        # print(query_tmp)
        if query_tmp:
            if query_tmp[0]['log_time'] != log_time:
                return 'update', my_mongo.update(filter={'fail_ip': ip}, update={"$set": {'log_time': log_time}})
            else:
                return 'equal no ops', None
        else:
            tmp = {}
            tmp['log_time'] = log_time
            tmp['fail_ip'] = ip
            return 'insert', my_mongo.insert(tmp)

    # IPAM失败IP(list格式)批量写入
    @staticmethod
    def post_fail_ip_bulk(fail_ip_doc):
        format_doc = []
        for data in fail_ip_doc:
            tmp = {}
            tmp['log_time'] = datetime.now().strftime("%Y-%m-%d")
            tmp['success_ip'] = data
            format_doc.append(tmp)

        my_mongo = MongoOps(db='IPAMData', coll='ipam_fail_ip')
        my_mongo.delete()
        my_mongo.insert_many(format_doc)
        doc_num = my_mongo.count_documents()

        return doc_num

    # IPAM更新IP单条数据落库专用
    @staticmethod
    def post_update_ip(ip):
        """
        1、查询除log_time字段外，是否有完全匹配，如果有就只更新log_time字段, 如果log_time字段一致，则不进行任何操作
        2、如果查询不到数据，则新增该字段
        """
        log_time = datetime.now().strftime("%Y-%m-%d")
        my_mongo = MongoOps(db='IPAMData', coll='netaxe_ipam_update_ip')
        query_tmp = my_mongo.find(query_dict={'update_ip': ip})
        # print(query_tmp)
        if query_tmp:
            if query_tmp[0]['log_time'] != log_time:
                return 'update', my_mongo.update(filter={'update_ip': ip}, update={"$set": {'log_time': log_time}})
            else:
                return 'equal no ops', None
        else:
            tmp = {}
            tmp['log_time'] = log_time
            tmp['update_ip'] = ip
            return 'insert', my_mongo.insert(tmp)

    # IPAM批量读取coll内容，比如netaxe_ipam_success_ip、netaxe_ipam_fail_ip
    @staticmethod
    def get_bulk(coll):
        my_mongo = MongoOps(db='IPAMData', coll=coll)
        res = my_mongo.find(fileds={'_id': 0})
        if res:
            return res
        else:
            return False

    # 获取指定coll的数据总数
    @staticmethod
    def get_coll_account(coll):
        my_mongo = MongoOps(db='IPAMData', coll=coll)
        doc_num = my_mongo.count_documents()
        return doc_num

    # 删除指定coll的所有数据
    @staticmethod
    def delet_coll(coll):
        my_mongo = MongoOps(db='IPAMData', coll=coll)
        my_mongo.delete()

        return


# 寻觅操作集合
class XunMiOps(object):

    # 重建寻觅索引 是否每次都要重建索引
    # https://www.itbaoku.cn/post/904737/do
    @staticmethod
    def xunmi_reindex():
        """
        {"node_hostname":"B3.NET.INT.ED.001",
        "node_ip":"10.254.12.10",
        "idc_name":"合肥B3",
        "node_interface":"M-GigabitEthernet0/0/0",
        "node_location":"运营商机房1_B02_35U",
        "server_ip_address":"10.254.12.68",
        "server_mac_address":"882a-5e62-c4b8",
        "server_admin":"",
        "server_platform":"",
        "server_location":"",
        "server_managername":"",
        "attribute":"生产网"}
        :return:
        """
        my_mongo = MongoOps(db='netops', coll='XunMi')
        # my_mongo.list_indexes()
        my_mongo.rebuild_index()
        # my_mongo.drop_indexes()
        # my_mongo.create_index([('log_time', pymongo.DESCENDING)])
        # my_mongo.create_index("server_ip_address")
        # my_mongo.create_index("node_hostname")
        # my_mongo.create_index("node_ip")
        # my_mongo.create_index("idc_name")
        # my_mongo.create_index("node_interface")
        # my_mongo.create_index("node_location")
        # my_mongo.create_index("server_ip_address")
        # my_mongo.create_index("server_mac_address")
        # my_mongo.create_index("server_admin")
        # my_mongo.create_index("server_platform")
        # my_mongo.create_index("server_location")
        # my_mongo.create_index("server_managername")
        # my_mongo.create_index("attribute")
        # my_mongo.create_index([('node_hostname', pymongo.DESCENDING),
        #                        ('node_ip', pymongo.DESCENDING),
        #                        ('idc_name', pymongo.DESCENDING),
        #                        ('node_interface', pymongo.DESCENDING),
        #                        ('node_location', pymongo.DESCENDING),
        #                        ('server_ip_address', pymongo.DESCENDING),
        #                        ('server_mac_address', pymongo.DESCENDING),
        #                        ('server_admin', pymongo.DESCENDING),
        #                        ('server_platform', pymongo.DESCENDING),
        #                        ('server_location', pymongo.DESCENDING),
        #                        ('server_managername', pymongo.DESCENDING),
        #                        ('attribute', pymongo.DESCENDING)])
        return

    @staticmethod
    def layer3interface_reindex():
        my_mongo = MongoOps(db='Automation', coll='layer3interface')
        my_mongo.rebuild_index()
        # my_mongo.drop_indexes()
        # my_mongo.create_index("ipaddress")
        # my_mongo.create_index("hostip")
        return

    @staticmethod
    def get_cmdb(data):
        my_mongo = MongoOps(db='XunMiData', coll='networkdevice')
        res = my_mongo.find(query_dict=data, fileds={'_id': 0})
        if res:
            return res
        else:
            return False

    @staticmethod
    def clear_cmdb():
        xunmi_total_ip_mongo = MongoOps(db='XunMiData', coll='networkdevice')
        xunmi_total_ip_mongo.delete()
        return

    @staticmethod
    def post_cmdb(data):
        cmdb_mongo = MongoOps(db='XunMiData', coll='networkdevice')
        if len(data) > 0:
            cmdb_mongo.delete()
            cmdb_mongo.insert_many(data)
            cmdb_mongo.rebuild_index()
            # cmdb_mongo.drop_indexes()
            # cmdb_mongo.create_index("manage_ip")
        # cmdb_mongo.close_client()
        return

    @staticmethod
    def delete_total_ip_list():
        xunmi_total_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_total_ip')
        return xunmi_total_ip_mongo.delete()

    @staticmethod
    def delete_success_ip_list():
        xunmi_success_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_success_ip')
        return xunmi_success_ip_mongo.delete()

    @staticmethod
    def all_total_ip_list():
        xunmi_total_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_total_ip')
        return xunmi_total_ip_mongo.find(fileds={'_id': 0})

    @staticmethod
    def all_success_ip_list():
        xunmi_success_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_success_ip')
        return xunmi_success_ip_mongo.find(fileds={'_id': 0})

    @staticmethod
    def post_success_ip_list(data):
        xunmi_success_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_success_ip')
        xunmi_success_ip_mongo.insert_many(data)
        return

    @staticmethod
    def xunmi_ops(**kwargs):
        """
        寻觅落库专用
        1、查询除log_time字段外，是否有完全匹配，如果有就只更新log_time字段, 如果log_time字段一致，则不进行任何操作
        2、如果查询不到数据，则新增该字段
        :param kwargs:
        :return:
        """
        log_time = kwargs['log_time']
        print(kwargs)
        kwargs.pop('log_time')
        query_tmp = xunmi_mongo.find(query_dict=kwargs)
        if query_tmp:
            if query_tmp[0]['log_time'] != log_time:
                xunmi_mongo.update(filter=kwargs, update={"$set": {'log_time': log_time}})
                return 'update'
            else:
                return 'equal no ops', None  # return ('equal no ops', None) 相同无需操作
        else:
            kwargs['log_time'] = log_time
            xunmi_mongo.insert(kwargs)
            return 'insert'  # return ('insert', ObjectId('5ef365baf700c65747d5ce62'))

    @staticmethod
    def post_total_ip_list(serverip_doc):
        """
        寻觅服务器IP批量写入list
        :param serverip_doc:
        :return:
        """
        format_doc = []
        for data in serverip_doc:
            tmp = {}
            tmp['log_time'] = datetime.now().strftime("%Y-%m-%d")
            tmp['server_ip'] = data
            format_doc.append(tmp)

        my_mongo = MongoOps(db='XunMiData', coll='xunmi_total_ip')
        if len(format_doc) >= 1000:
            my_mongo.delete()
            my_mongo.insert_many(format_doc)
        doc_num = my_mongo.count_documents()
        return doc_num

    @staticmethod
    def total_server_ip():
        total_ip_mongo = MongoOps(db='XunMiData', coll='xunmi_total_ip')
        res = total_ip_mongo.find(fileds={'_id': 0})
        if res:
            return res
        else:
            return False

    # 根据服务器IP 查询寻觅信息接口
    @staticmethod
    def get_serverip_xunmi_info(server_ip):
        res = {}
        my_mongo = MongoOps(db='netops', coll='XunMi')
        data = dict(
            server_ip_address=server_ip,
        )
        tmp = my_mongo.find_re(data, fileds={'_id': 0}, sort='log_time')
        if tmp:
            res = tmp[-1]

        return res