import json
from uuid import uuid4
from django.db import transaction
from rest_framework.views import APIView
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from netaddr import IPAddress
from netaxe.settings import DEBUG
from apps.asset.models import AssetIpInfo
from apps.dcs_control.tasks import FirewallMain, SecPolicyMain
from utils.db.mongo_ops import MongoNetOps, MongoOps
from apps.dcs_control.jsonschema import single_json_validate
from apps.dcs_control.json_validate.deny_by_addr_obj import deny_schema
from apps.dcs_control.json_validate.address_schema import address_schema
from apps.dcs_control.json_validate.dnat_schema import post_dnat_schema
from apps.dcs_control.json_validate.service_schema import service_schema
from apps.dcs_control.json_validate.sec_policy import sec_policy_schema
from apps.dcs_control.tasks import bulk_deny_by_address, address_set, config_dnat, config_sec_policy
from apps.dcs_control.db import (
    hillstone_dnat_mongo, snat_mongo, sec_policy_mongo, dnat_mongo,
    address_mongo, service_mongo, predefined_mongo, zone_mongo,
)
from apps.dcs_control.constants import Vendor
from apps.dcs_control.models import FirewallPolicyAuditRecord
from apps.dcs_control.serializers import FirewallPolicyAuditRecordSerializer
from apps.automation.models import AutoFlow
from apps.dcs_control.policy_audit import (
    build_sec_policy_audit_payload,
    extract_sec_policy_audit_summary,
    extract_sec_policy_findings,
    get_vendor_aliases,
)

if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config'


# 一键封堵
class DenyByAddrObj(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        if 'vendor' in get_param:
            get_param['vendor'] = Vendor.normalize(get_param['vendor'])
        # 查询策略包含指定的地址对象的策略匹配次数
        if all(k in get_param for k in ("vendor", "hostip", "address_book")):
            if get_param['vendor'] in Vendor.choices():
                real_ip = AssetIpInfo.objects.select_related('device').filter(
                    name='HA', ipaddr=get_param['hostip'],
                    device__ha_status__in=[0, 1]).values('device__manage_ip').first()
                if real_ip:
                    res = MongoNetOps.query_sec_policy_count(get_param['vendor'], real_ip['device__manage_ip'],
                                                             get_param['address_book'])
                else:
                    res = MongoNetOps.query_sec_policy_count(get_param['vendor'], get_param['hostip'],
                                                             get_param['address_book'])
                if isinstance(res, int):
                    return JsonResponse({'code': 200,
                                         'data': {'hostip': get_param['hostip'],
                                                  'address_book': get_param['address_book'],
                                                  'count': res}, 'msg': 'ok'})
                else:
                    return JsonResponse({'code': 400, 'msg': '未查询到匹配的数据'})
            else:
                return JsonResponse({'code': 400, 'msg': f'vendor 必须是 {Vendor.choices()} 其中一个'})

    def post(self, request):
        post_param = request.data
        # 一键封堵操作
        schema_res, msg = single_json_validate(post_param, deny_schema)
        # json数据验证通过
        if schema_res:
            post_param['origin'] = "DCS控制器"
            post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
            post_param['user'] = str(request.user.username)
            res = bulk_deny_by_address.apply_async(kwargs=post_param, queue=CELERY_QUEUE)  # config_backup
            if str(res) == 'None':
                print('forget')
                res.forget()
                return JsonResponse({'code': 400, 'message': '重复的任务参数', 'data': []})
            if res:
                return JsonResponse({'code': 200, 'message': 'OK', 'data': str(res)})
        else:
            return JsonResponse(msg, safe=False)
        return JsonResponse(dict(code=400, message='操作不被允许', data=[]))


class AddressSet(APIView):
    permission_classes = ()

    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'vendor' in get_param:
            get_param['vendor'] = Vendor.normalize(get_param['vendor'])
        # 获取单个设备地址组信息
        if all(k in get_param for k in ("vendor", "hostip")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_h3c_address_obj()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_huawei_address_obj()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                _res = address_mongo \
                    .find(query_dict=dict(hostip=get_param['hostip']), fields={'_id': 0})
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 400})
        return JsonResponse({'code': 400, 'data': [], 'message': '没有匹配'})

    def post(self, request):
        # 你应该使用request.data. 它更灵活，涵盖更多用例，并且可以根据需要多次访问
        # https://stackoverflow.com/questions/36616309/request-data-in-drf-vs-request-body-in-django
        print(request.META.get('CONTENT_TYPE'))
        print(request.user)
        remote_ip = request.META.get("REMOTE_ADDR")
        post_param = request.data
        if 'vendor' in post_param:
            post_param['vendor'] = Vendor.normalize(post_param['vendor'])
        # 更新单个设备地址组信息(山石)
        if all(k in post_param for k in ("vendor", "update_device", "hostip")):
            if post_param['vendor'] == 'Hillstone':
                _res = SecPolicyMain.update_hillstone_addr_service(post_param['hostip'])
                return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'result': 'OK'}),
                                    content_type="application/json")
            return HttpResponse(json.dumps(dict(code=400, message='操作不被允许')), content_type="application/json")

        # 单个地址对象新增条目(新)
        if all(k in post_param for k in ("vendor", "hostip", "hostid")):
            schema_res, msg = single_json_validate(post_param, address_schema)
            # print(schema_res)
            # 新建地址对象必须携带 ip_mask 或者 range_start/range_end 二选一，否则无法新建
            if 'add_object' in post_param.keys():
                if 'ip_mask' not in post_param.keys() and 'range_start' not in post_param.keys():
                    return HttpResponse(
                        json.dumps({'code': 400,
                                    'data': 'ip_mask or range_start/range_end',
                                    'message': 'create object must get "ip_mask" or "range_start/range_end'
                                    }), content_type="application/json")
            # json数据验证通过
            if schema_res:
                post_param['user'] = str(request.user.username)
                post_param['remote_ip'] = str(remote_ip)
                res = address_set.apply_async(kwargs=post_param, queue=CELERY_QUEUE,
                                              retry=True)  # config_backup
                if str(res) == 'None':
                    print('forget')
                    res.forget()
                    return HttpResponse(json.dumps({'code': 400,
                                                    'message': '重复的任务参数', 'data': []}),
                                        content_type="application/json")
                if res:
                    return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'data': str(res)}),
                                        content_type="application/json")
            else:
                return JsonResponse(msg, safe=False)
            return HttpResponse(json.dumps(dict(code=400, message='操作不被允许', data=[])),
                                content_type="application/json")

        return JsonResponse(dict(code=400, message='没有任何匹配'))


class ServiceSet(APIView):
    permission_classes = ()

    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'vendor' in get_param:
            get_param['vendor'] = Vendor.normalize(get_param['vendor'])
        # 获取单个设备地址组信息
        if all(k in get_param for k in ("vendor", "hostip")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_h3c_service_obj()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_huawei_service_obj()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                _res = service_mongo \
                    .find(query_dict=dict(hostip=get_param['hostip']), fields={'_id': 0})
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 400})
        return JsonResponse({'code': 400, 'data': [], 'message': '没有匹配'})

    def post(self, request):
        # 你应该使用request.data. 它更灵活，涵盖更多用例，并且可以根据需要多次访问
        # https://stackoverflow.com/questions/36616309/request-data-in-drf-vs-request-body-in-django
        print(request.META.get('CONTENT_TYPE'))
        print(request.user)
        remote_ip = request.META.get("REMOTE_ADDR")
        post_param = request.data
        if 'vendor' in post_param:
            post_param['vendor'] = Vendor.normalize(post_param['vendor'])
        # 更新单个设备服务信息(山石)
        if all(k in post_param for k in ("vendor", "update_device", "hostip")):
            if post_param['vendor'] == 'Hillstone':
                _res = SecPolicyMain.update_hillstone_addr_service(post_param['hostip'])
                return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'result': 'OK'}),
                                    content_type="application/json")
            return HttpResponse(json.dumps(dict(code=400, message='操作不被允许')), content_type="application/json")

        # 单个服务对象新增条目(新)
        if all(k in post_param for k in ("vendor", "hostip", "hostid")):
            schema_res, msg = single_json_validate(post_param, service_schema)
            # print(schema_res)
            # 新建地址对象必须携带 ip_mask 或者 range_start/range_end 二选一，否则无法新建
            if 'add_object' in post_param.keys():
                if 'ip_mask' not in post_param.keys() and 'range_start' not in post_param.keys():
                    return HttpResponse(
                        json.dumps({'code': 400,
                                    'data': 'ip_mask or range_start/range_end',
                                    'message': 'create object must get "ip_mask" or "range_start/range_end'
                                    }), content_type="application/json")
            # json数据验证通过
            if schema_res:
                post_param['user'] = str(request.user.username)
                post_param['remote_ip'] = str(remote_ip)
                res = address_set.apply_async(kwargs=post_param, queue=CELERY_QUEUE,
                                              retry=True)  # config_backup
                if str(res) == 'None':
                    print('forget')
                    res.forget()
                    return HttpResponse(json.dumps({'code': 400,
                                                    'message': '重复的任务参数', 'data': []}),
                                        content_type="application/json")
                if res:
                    return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'data': str(res)}),
                                        content_type="application/json")
            else:
                return JsonResponse(msg, safe=False)
            return HttpResponse(json.dumps(dict(code=400, message='操作不被允许', data=[])),
                                content_type="application/json")

        return JsonResponse(dict(code=400, message='没有任何匹配'))


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class DestAddTranslate(APIView):
    permission_classes = ()

    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        if 'vendor' in get_param:
            get_param['vendor'] = Vendor.normalize(get_param['vendor'])
        dnat_range_filters = ('global_ip', 'global_port', 'local_ip', 'local_port')
        if get_param.get('hostip') and (
            any(get_param.get(key) for key in dnat_range_filters) or 'vendor' not in get_param
        ):
            try:
                query = {'hostip': get_param['hostip']}

                if get_param.get('global_ip'):
                    global_ip_int = IPAddress(get_param['global_ip']).value
                    query['global_ip'] = {
                        '$elemMatch': {
                            'start_int': {'$lte': global_ip_int},
                            'end_int': {'$gte': global_ip_int},
                        }
                    }

                if get_param.get('local_ip'):
                    local_ip_int = IPAddress(get_param['local_ip']).value
                    query['local_ip'] = {
                        '$elemMatch': {
                            'start_int': {'$lte': local_ip_int},
                            'end_int': {'$gte': local_ip_int},
                        }
                    }

                if get_param.get('global_port'):
                    global_port = int(get_param['global_port'])
                    query['global_port'] = {
                        '$elemMatch': {
                            'start': {'$lte': global_port},
                            'end': {'$gte': global_port},
                        }
                    }

                if get_param.get('local_port'):
                    local_port = int(get_param['local_port'])
                    query['local_port'] = {
                        '$elemMatch': {
                            'start': {'$lte': local_port},
                            'end': {'$gte': local_port},
                        }
                    }
                _res = dnat_mongo.find(query_dict=query, fields={'_id': 0})
                return JsonResponse({
                    'results': _res,
                    'count': len(_res),
                    'code': 200,
                    'msg': 'success',
                })
            except Exception as e:
                return JsonResponse({
                    'results': [],
                    'count': 0,
                    'code': 400,
                    'msg': f'参数错误: {str(e)}',
                })
        # print(get_param)
        # 获取单个设备DNAT信息
        if all(k in get_param for k in ("vendor", "hostip")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_h3c_global_dnat()
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 400})
            elif get_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_huawei_nat_server()
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 400})
            elif get_param['vendor'] == 'Hillstone':
                _res = hillstone_dnat_mongo.find(query_dict=dict(hostip=get_param['hostip']), fileds={'_id': 0})
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res),
                                         'code': 400})
        return JsonResponse({'code': 200})

    def _normalize_post_param(self, request):
        post_param = request.data
        if 'vendor' in post_param:
            post_param['vendor'] = Vendor.normalize(post_param['vendor'])
        return post_param

    def _handle_update_device_sync(self, post_param):
        if post_param['vendor'] == 'Hillstone':
            config_dnat.run(**post_param)
            return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'result': 'OK'}),
                                content_type="application/json")
        return JsonResponse(dict(code=400, message='操作不被允许'))

    def _handle_dnat_sync(self, request, post_param):
        schema_res, msg = single_json_validate(post_param, post_dnat_schema)
        if not schema_res:
            return JsonResponse(msg, safe=False)

        post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
        post_param['user'] = str(request.user.username)
        post_param['task_id'] = post_param.get('task_id') or str(uuid4())
        flow_record = config_dnat.run(**post_param)
        if not flow_record:
            return JsonResponse({'code': 400, 'message': 'DNAT执行失败，请查看服务端日志', 'data': []})
        flow_data = AutoFlow.objects.filter(id=flow_record.id).values().first()
        if flow_data:
            callback_result = getattr(flow_record, 'callback_result', None) or {}
            if callback_result and not callback_result.get('ok') and not callback_result.get('skipped'):
                return JsonResponse({
                    'code': 200,
                    'message': f"DNAT下发成功，但回调失败: {callback_result.get('error')}",
                    'data': flow_data,
                })
            return JsonResponse({'code': 200, 'message': 'OK', 'data': flow_data})
        return JsonResponse({'code': 400, 'message': '未查询到流程记录', 'data': []})

    # 表单验证
    def post(self, request):
        post_param = self._normalize_post_param(request)
        # 更新单个设备DNAT信息
        if all(k in post_param for k in ("vendor", "update_device", "hostip")):
            return self._handle_update_device_sync(post_param)
        # DNAT操作
        if all(k in post_param for k in ("vendor", "hostip", "hostid")):
            return self._handle_dnat_sync(request, post_param)

        return JsonResponse(dict(code=400, message='没有任何匹配'))


class DestAddTranslateAsync(DestAddTranslate):
    def _handle_update_device_sync(self, post_param):
        if post_param['vendor'] == 'Hillstone':
            res = config_dnat.apply_async(kwargs=post_param, queue=CELERY_QUEUE, retry=True)
            if str(res) == 'None':
                return JsonResponse({'code': 400, 'message': '重复的任务参数', 'data': []})
            return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'result': str(res)}),
                                content_type="application/json")
        return JsonResponse(dict(code=400, message='操作不被允许'))

    def _handle_dnat_sync(self, request, post_param):
        schema_res, msg = single_json_validate(post_param, post_dnat_schema)
        if not schema_res:
            return JsonResponse(msg, safe=False)

        post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
        post_param['user'] = str(request.user.username)
        res = config_dnat.apply_async(kwargs=post_param, queue=CELERY_QUEUE, retry=True)
        if str(res) == 'None':
            return JsonResponse({'code': 400, 'message': '重复的任务参数', 'data': []})
        return JsonResponse({'code': 200, 'message': 'OK', 'data': str(res)})


class SecPolicy(APIView):
    permission_classes = ()

    authentication_classes = ()

    def get(self, request):
        """

        :param request:
        :return:
        """
        get_param = request.GET.dict()
        if 'vendor' in get_param:
            get_param['vendor'] = Vendor.normalize(get_param['vendor'])
        print(get_param)
        if all(k in get_param for k in ("page_size", "page")):
            _params = json.loads(get_param["query"])
            query = {}
            _query = {k: v for k, v in _params.items() if v}
            if 'hostip' in _query.keys():
                query['hostip'] = _query['hostip']
            if 'id' in _query.keys():
                query['id'] = _query['id']
            if 'name' in _query.keys():
                query['name'] = _query['name']
            if 'src_ip' in _query.keys():
                _ip = IPAddress(_query['src_ip'])
                query['src_ip_split'] = {'$elemMatch': {'start': {'$lte': _ip.value}, 'end': {'$gte': _ip.value}}}
            elif _query.get('src_ip') or _query.get('dst_ip'):
                query['src_ip_split'] = {'$elemMatch': {'start': {'$lte': 4294967295}, 'end': {'$gte': 0}}}
            if 'dst_ip' in _query.keys():
                _ip = IPAddress(_query['dst_ip'])
                query['dst_ip_split'] = {'$elemMatch': {'start': {'$lte': _ip.value}, 'end': {'$gte': _ip.value}}}
            elif _query.get('src_ip') or _query.get('dst_ip'):
                query['dst_ip_split'] = {'$elemMatch': {'start': {'$lte': 4294967295}, 'end': {'$gte': 0}}}
            # print(query)
            res = sec_policy_mongo.find_page_query(query_dict=query,
                                                   fields={'_id': 0}, page_size=int(get_param['page_size']),
                                                   page_num=int(get_param['page']))
            count = sec_policy_mongo.count_documents(query=query)
            result = {
                'code': 200,
                'msg': 'success',
                'data': res,
                'count': count
            }
            return JsonResponse(result, safe=True)

        # if all(k in get_param for k in ("hostip", "sec_policy")):
        # 获取防火墙设备列表，筛选HA状态为独立设备或主设备，类型为防火墙的设备列表。
        if 'get_firewall_sec_policy' in get_param.keys():
            _res = sec_policy_mongo \
                .find(query_dict=dict(hostip=get_param['get_firewall_sec_policy']), fields={'_id': 0})
            if _res:
                res = json.dumps({'results': _res, 'count': len(_res),
                                  'code': 200})
            else:
                res = json.dumps({'results': _res, 'count': len(_res),
                                  'code': 400})
            return HttpResponse(res, content_type="application/json")
        if 'get_firewall_sec_policy_id' in get_param.keys():
            _res = sec_policy_mongo \
                .find(query_dict=dict(hostip=get_param['get_firewall_sec_policy_id']), fields={'_id': 0,
                                                                                               'id': 1,
                                                                                               'name': 1})
            if _res:
                res = json.dumps({'results': _res, 'count': len(_res),
                                  'code': 200})
            else:
                res = json.dumps({'results': _res, 'count': len(_res),
                                  'code': 400})
            return HttpResponse(res, content_type="application/json")
        # 获取设备安全域列表
        if all(k in get_param for k in ("vendor", "get_sec_zone")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['get_sec_zone'])
                _res = _FirewallMain.get_h3c_sec_zone()
                if isinstance(_res, list):
                    res = json.dumps({'data': [{'name': x['Name']} for x in _res], 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'data': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _res = SecPolicyMain.get_huawei_sec_zone(get_param['get_sec_zone'])
                if isinstance(_res, list):
                    res = json.dumps({'data': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                _res = zone_mongo.find(
                    query_dict=dict(hostip=get_param['get_sec_zone'], type='L3'), fields={'_id': 0})
                if _res:
                    res = json.dumps({'data': _res, 'count': len(_res),
                                      'code': 200, 'msg': '成功'})
                else:
                    res = json.dumps({'data': _res, 'count': len(_res),
                                      'code': 400, 'msg': '没有该防火墙安全域数据'})
                return HttpResponse(res, content_type="application/json")
        # 获取设备地址组
        if all(k in get_param for k in ("vendor", "get_address_obj")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['get_address_obj'])
                _res = _FirewallMain.get_h3c_address_obj()
                if isinstance(_res, list):
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(get_param['get_address_obj'])
                _res = _FirewallMain.get_huawei_address_obj()
                if isinstance(_res, list):
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                _res = MongoOps(db='Automation', coll='Hillstone_address') \
                    .find(query_dict=dict(hostip=get_param['get_address_obj']), fields={'_id': 0})
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
        # 获取设备服务组
        if all(k in get_param for k in ("vendor", "get_service_obj")):
            if get_param['vendor'] == 'H3C':
                service_res = []
                _res = SecPolicyMain.get_h3c_service_obj(get_param['get_service_obj'])
                service_res.append({
                    'label': '自定义服务',
                    'options': [{'label': x['Name'], 'value': x['Name'], 'protocol': ''}
                                for x in _res] + [{'label': 'Any', 'value': 'Any', 'protocol': ''}]
                })
                if service_res:
                    res = json.dumps({'data': service_res, 'count': len(service_res),
                                      'code': 200, 'msg': '成功'})
                else:
                    res = json.dumps({'data': service_res, 'count': len(service_res),
                                      'code': 400, 'msg': '没有该防火墙服务对象数据'})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _res = SecPolicyMain.get_huawei_service_obj(get_param['get_service_obj'])
                if isinstance(_res, list):
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                service_res = []
                custom_services = service_mongo \
                    .find(query_dict=dict(hostip=get_param['get_service_obj']), fields={'_id': 0})
                predefined_services = predefined_mongo \
                    .find(query_dict=dict(hostip=get_param['get_service_obj']), fields={'_id': 0})
                custom_services_options = []
                for x in custom_services:
                    protocol_parts = []
                    for a in x['items']:
                        if a.get('dst-port-max', ''):
                            protocol_str = f"{a['protocol']}:{a.get('dst-port-min', '')}-{a.get('dst-port-max', '')}"
                        else:
                            protocol_str = f"{a['protocol']}:{a.get('dst-port-min', '')}"
                        protocol_parts.append(protocol_str)

                    item = {
                        'label': x['name'],
                        'value': x['name'],
                        'protocol': ','.join(protocol_parts)
                    }
                    custom_services_options.append(item)

                predefined_services_options = []
                for x in predefined_services:
                    protocol_parts = []
                    for a in x['items']:
                        if a.get('dst-port-max', ''):
                            protocol_str = f"{a['protocol']}:{a.get('dst-port-min', '')}-{a.get('dst-port-max', '')}"
                        else:
                            protocol_str = f"{a['protocol']}:{a.get('dst-port-min', '')}"
                        protocol_parts.append(protocol_str)

                    item = {
                        'label': x['name'],
                        'value': x['name'],
                        'protocol': ','.join(protocol_parts)
                    }
                    predefined_services_options.append(item)
                service_res.append({
                    'label': '自定义服务',
                    'options': custom_services_options
                })
                service_res.append({
                    'label': '预定义服务',
                    'options': predefined_services_options + [{'label': 'Any', 'value': 'Any', 'protocol': ''}]
                })
                if service_res:
                    res = json.dumps({'data': service_res, 'count': len(service_res),
                                      'code': 200, 'msg': '成功'})
                else:
                    res = json.dumps({'data': service_res, 'count': len(service_res),
                                      'code': 400, 'msg': '没有该防火墙服务对象数据'})
                return HttpResponse(res, content_type="application/json")
        # 获取单个设备安全策略
        if all(k in get_param for k in ("vendor", "hostip")):
            if get_param['vendor'] == 'H3C':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_h3c_sec_policy()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(get_param['hostip'])
                _res = _FirewallMain.get_huawei_sec_policy()
                if _res:
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': _res, 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif get_param['vendor'] == 'Hillstone':
                _res = sec_policy_mongo \
                    .find(query_dict=dict(hostip=get_param['hostip']), fields={'_id': 0})
                if _res:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 200})
                else:
                    return JsonResponse({'results': _res, 'count': len(_res), 'code': 400})
        return JsonResponse({'code': 400}, content_type="application/json")

    def post(self, request):
        post_param = request.data
        if 'vendor' in post_param:
            post_param['vendor'] = Vendor.normalize(post_param['vendor'])
        risks_port = [23, 22, 20, 21, 3306, 1521, 6379, 1433, 445, 3389, 5432]
        # print(post_param)
        # 获取设备地址组
        if all(k in post_param for k in ("vendor", "hostip", "name", "id")):
            if post_param['vendor'] == 'H3C':
                type_map = {
                    '0': 'Nested group',
                    '1': 'protocol',
                    '2': 'icmp',
                    '3': 'tcp',
                    '4': 'udp',
                    '5': 'icmpv6',
                }
                result = {
                    'src_addr': [],
                    'dst_addr': [],
                    'service': []
                }
                if post_param['src_addr']:
                    for addr in post_param['src_addr']:
                        if 'object' in addr.keys():
                            # src_addr_query = _FirewallMain.get_h3c_address_obj(name=addr['object'])
                            src_addr_query = MongoOps(db='NETCONF', coll='h3c_address_set').find(
                                query_dict=dict(hostip=post_param['hostip'], Name=addr['object']), fields={'_id': 0}
                            )
                            if src_addr_query:
                                for x in src_addr_query[0]['ObjList']:
                                    if x['Type'] == 'ip':
                                        result['src_addr'].append({
                                            'name': addr['object'],
                                            'ip': x['HostIPv4Address'],
                                            'xunmi': MongoNetOps.get_xunmi_info(
                                                dict(server_ip_address=x['HostIPv4Address']))
                                        })
                if post_param['dst_addr']:
                    for addr in post_param['dst_addr']:
                        if 'object' in addr.keys():
                            # dst_addr_query = _FirewallMain.get_h3c_address_obj(name=addr['object'])
                            dst_addr_query = MongoOps(db='NETCONF', coll='h3c_address_set').find(
                                query_dict=dict(hostip=post_param['hostip'], Name=addr['object']), fields={'_id': 0}
                            )
                            if dst_addr_query:
                                for x in dst_addr_query[0]['ObjList']:
                                    if x['Type'] == 'ip':
                                        result['dst_addr'].append({
                                            'name': addr['object'],
                                            'ip': x['HostIPv4Address'],
                                            'xunmi': MongoNetOps.get_xunmi_info(
                                                dict(server_ip_address=x['HostIPv4Address']))
                                        })
                if post_param['service']:
                    for ser in post_param['service']:
                        if 'object' in ser.keys():
                            service_query = MongoOps(db='NETCONF', coll='h3c_service_set').find(
                                query_dict=dict(hostip=post_param['hostip'], Name=ser['object']), fields={'_id': 0}
                            )
                            if service_query:
                                for _service_query in service_query:
                                    for items in _service_query['items']:
                                        security_type = 'default'
                                        port = items['EndDestPort']
                                        if port in risks_port:
                                            security_type = 'warning'
                                        if items['StartDestPort'] != items['EndDestPort']:
                                            port = f"{items['StartDestPort']}-{items['EndDestPort']}"
                                            for i in range(int(items['StartDestPort']), int(items['EndDestPort']) + 1):
                                                if i in risks_port:
                                                    security_type = 'warning'
                                        result['service'].append({
                                            'name': _service_query['Name'],
                                            'protocol': type_map[items['Type']] if items['Type'] in type_map.keys() else
                                            items['Type'],
                                            'port': port,
                                            'type': security_type
                                        })
                return JsonResponse({'code': 200, 'data': result, 'msg': 'ok'}, content_type="application/json")
            elif post_param['vendor'] == 'Huawei':
                _FirewallMain = FirewallMain(post_param['hostip'])
                _res = _FirewallMain.get_huawei_address_obj()
                if isinstance(_res, list):
                    res = json.dumps({'results': _res, 'count': len(_res),
                                      'code': 200})
                else:
                    res = json.dumps({'results': [], 'count': 0,
                                      'code': 400})
                return HttpResponse(res, content_type="application/json")
            elif post_param['vendor'] == Vendor.HILLSTONE:
                result = {
                    'src_addr': [],
                    'dst_addr': [],
                    'service': []
                }
                if post_param['src_addr']:
                    for addr in post_param['src_addr']:
                        if 'object' in addr.keys():
                            src_addr_query = address_mongo.find(
                                query_dict=dict(hostip=post_param['hostip'], name=addr['object']), fields={'_id': 0}
                            )
                            if src_addr_query:
                                if 'ip' in src_addr_query[0].keys():
                                    for x in src_addr_query[0]['ip']:
                                        if 'ip' in x.keys():
                                            result['src_addr'].append({
                                                'name': addr['object'],
                                                'ip': x['ip'],
                                                'xunmi': MongoNetOps.get_xunmi_info(
                                                    dict(server_ip_address=x['ip'].split('/')[0]))
                                            })
                                if 'range' in src_addr_query[0].keys():
                                    for x in src_addr_query[0]['range']:
                                        if 'start' in x.keys():
                                            result['dst_addr'].append({
                                                'name': addr['object'],
                                                'ip': f"{x['start']}-{x['end']}",
                                                'xunmi': ''
                                            })
                        if 'ip' in addr.keys():
                            result['src_addr'].append({
                                'name': '',
                                'ip': addr['ip'],
                                'xunmi': MongoNetOps.get_xunmi_info(dict(server_ip_address=addr['ip'].split('/')[0]))
                            })
                if post_param['dst_addr']:
                    for addr in post_param['dst_addr']:
                        if 'object' in addr.keys():
                            src_addr_query = address_mongo.find(
                                query_dict=dict(hostip=post_param['hostip'], name=addr['object']), fields={'_id': 0}
                            )
                            if src_addr_query:
                                if 'ip' in src_addr_query[0].keys():
                                    for x in src_addr_query[0]['ip']:
                                        if 'ip' in x.keys():
                                            result['dst_addr'].append({
                                                'name': addr['object'],
                                                'ip': x['ip'],
                                                'xunmi': MongoNetOps.get_xunmi_info(
                                                    dict(server_ip_address=x['ip'].split('/')[0]))
                                            })
                                if 'range' in src_addr_query[0].keys():
                                    for x in src_addr_query[0]['range']:
                                        if 'start' in x.keys():
                                            result['dst_addr'].append({
                                                'name': addr['object'],
                                                'ip': f"{x['start']}-{x['end']}",
                                                'xunmi': ''
                                            })
                        if 'ip' in addr.keys():
                            result['dst_addr'].append({
                                'name': '',
                                'ip': addr['ip'],
                                'xunmi': MongoNetOps.get_xunmi_info(dict(server_ip_address=addr['ip'].split('/')[0]))
                            })
                if post_param['service']:
                    for ser in post_param['service']:
                        if 'object' in ser.keys():
                            service_query = service_mongo.find(
                                query_dict=dict(hostip=post_param['hostip'], name=ser['object']), fields={'_id': 0}
                            )
                            if not service_query:
                                service_query = predefined_mongo.find(
                                    query_dict=dict(hostip=post_param['hostip'], name=ser['object']), fields={'_id': 0}
                                )
                            if service_query:
                                for x in service_query[0]['items']:
                                    security_type = 'default'
                                    port = x['dst-port-min']
                                    if port in risks_port:
                                        security_type = 'warning'
                                    if x.get('dst-port-max') is not None:
                                        if x.get('dst-port-max') != x['dst-port-min']:
                                            port = f"{x['dst-port-min']}-{x['dst-port-max']}"
                                            for i in range(int(x['dst-port-min']), int(x['dst-port-max']) + 1):
                                                if i in risks_port:
                                                    security_type = 'warning'
                                    result['service'].append({
                                        'name': ser['object'],
                                        'port': port,
                                        'protocol': x['protocol'],
                                        'type': security_type
                                    })
                return JsonResponse({'code': 200, 'data': result, 'msg': 'ok'}, content_type="application/json")

        if all(k in post_param for k in ("vendor", "update_device")):
            if post_param['vendor'] == 'H3C':
                _res = SecPolicyMain.get_single_h3c(post_param['update_device'])
                if _res:
                    return HttpResponse(json.dumps(dict(code=200, msg='刷新成功', data=[])), content_type="application/json")
            elif post_param['vendor'] == 'Huawei':
                _res = SecPolicyMain.get_single_huawei(post_param['update_device'])
                if _res:
                    return HttpResponse(json.dumps(dict(code=200, msg='刷新成功', data=[])), content_type="application/json")
            elif post_param['vendor'] == 'Hillstone':
                _res = SecPolicyMain.get_single_hillstone(post_param['update_device'])
                if _res:
                    return HttpResponse(json.dumps(dict(code=200, msg='刷新成功', data=[])), content_type="application/json")
            return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
        if all(k in post_param for k in ("vendor", "hostid", "action")):
            schema_res, msg = single_json_validate(post_param, sec_policy_schema)
            # json数据验证通过
            if schema_res:
                post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
                post_param['user'] = str(request.user.username)
                res = config_sec_policy.apply_async(kwargs=post_param, queue=CELERY_QUEUE,
                                                    retry=True)  # config_backup
                if str(res) == 'None':
                    print('forget')
                    res.forget()
                    return JsonResponse({'code': 400, 'msg': '重复的任务参数', 'data': []})
                if res:
                    return JsonResponse({'code': 200, 'msg': 'OK', 'data': str(res)})
            else:
                return JsonResponse(msg, safe=False)
            return JsonResponse(dict(code=400, message='操作不被允许', data=[]))
        return JsonResponse({'code': 400}, content_type="application/json")


class SecPolicyAudit(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        hostip = get_param.get("hostip", "")
        vendor = get_param.get("vendor", "")
        if vendor:
            vendor = Vendor.normalize(vendor)

        if not hostip:
            return JsonResponse(
                {"code": 400, "message": "缺少必要参数: hostip", "data": None}
            )

        policies = sec_policy_mongo.find(
            query_dict=dict(hostip=hostip),
            fields={"_id": 0},
        )
        if vendor:
            vendor_aliases = get_vendor_aliases(vendor)
            policies = [
                item for item in policies
                if str(item.get("vendor", "")) in vendor_aliases
            ]

        payload = build_sec_policy_audit_payload(
            policies=policies,
            hostip=hostip,
            vendor=vendor,
        )
        return JsonResponse(
            {
                "code": 200,
                "message": "获取统一安全策略审计结果成功",
                "data": payload,
            }
        )


class SecPolicyAuditRecordView(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_param = request.GET.dict()
        queryset = FirewallPolicyAuditRecord.objects.all().order_by("-created_at")

        if get_param.get("device_ip"):
            queryset = queryset.filter(device_ip=get_param["device_ip"])
        if get_param.get("vendor"):
            queryset = queryset.filter(vendor=Vendor.normalize(get_param["vendor"]))
        if get_param.get("status"):
            queryset = queryset.filter(status=get_param["status"])
        if get_param.get("audit_type"):
            queryset = queryset.filter(audit_type=get_param["audit_type"])

        limit = int(get_param.get("limit", 20))
        serializer = FirewallPolicyAuditRecordSerializer(queryset[:limit], many=True)
        return JsonResponse(
            {
                "code": 200,
                "message": "获取防火墙审计记录成功",
                "data": serializer.data,
                "count": len(serializer.data),
            }
        )

    def post(self, request):
        post_param = request.data.copy()
        device_ip = post_param.get("device_ip") or post_param.get("hostip")
        vendor = post_param.get("vendor", "")
        if vendor:
            vendor = Vendor.normalize(vendor)

        if not device_ip:
            return JsonResponse(
                {"code": 400, "message": "缺少必要参数: device_ip/hostip", "data": None}
            )

        audit_payload = post_param.get("audit_payload")
        if not audit_payload:
            policies = sec_policy_mongo.find(
                query_dict=dict(hostip=device_ip),
                fields={"_id": 0},
            )
            if vendor:
                vendor_aliases = get_vendor_aliases(vendor)
                policies = [
                    item for item in policies
                    if str(item.get("vendor", "")) in vendor_aliases
                ]
            audit_payload = build_sec_policy_audit_payload(
                policies=policies,
                hostip=device_ip,
                vendor=vendor,
            )

        summary = post_param.get("summary") or extract_sec_policy_audit_summary(audit_payload)
        findings = post_param.get("findings") or extract_sec_policy_findings(audit_payload)
        status = post_param.get("status", FirewallPolicyAuditRecord.Status.SUCCESS)
        operator = post_param.get("operator") or getattr(getattr(request, "user", None), "username", "") or ""

        record_data = {
            "audit_type": post_param.get(
                "audit_type", FirewallPolicyAuditRecord.AuditType.SECURITY_POLICY
            ),
            "vendor": vendor or audit_payload.get("vendor", ""),
            "device_ip": device_ip,
            "operator": operator,
            "source": post_param.get("source", "NetClaw-CN"),
            "status": status,
            "summary": summary,
            "findings": findings,
            "audit_payload": audit_payload,
            "auto_flow_id": post_param.get("auto_flow_id"),
            "task_id": post_param.get("task_id", ""),
        }
        serializer = FirewallPolicyAuditRecordSerializer(data=record_data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save()

        return JsonResponse(
            {
                "code": 201,
                "message": "写入防火墙审计记录成功",
                "data": FirewallPolicyAuditRecordSerializer(record).data,
            }
        )
    #     # 更新单个设备策略
    #     if all(k in post_param for k in ("vendor", "update_device")):
    #         if post_param['vendor'] == 'H3C':
    #             _res = SecPolicyMain.get_single_h3c(post_param['update_device'])
    #             if _res:
    #                 return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #         elif post_param['vendor'] == 'Huawei':
    #             _res = SecPolicyMain.get_single_huawei(post_param['update_device'])
    #             if _res:
    #                 return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #         elif post_param['vendor'] == 'Hillstone':
    #             print("更新山石设备安全策略", post_param)
    #             _res = SecPolicyMain.get_single_hillstone(post_param['update_device'])
    #             if _res:
    #                 return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #         return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     # # 移动策略
    #     # if all(k in post_param for k in ("current_id", "target_id", "vendor", "insert", "hostip")):
    #     #     """
    #     #     insert 可以设置为 before/after/first/last（其中 before 代表移动到目标规则之前，after 代表移动到
    #     #     目标规则之后，first 代表移动规则至第一条，last 代表移动规则至最后一条）。当 insert 设置为
    #     #     before/after 时，必须同时指定目标规则（即指定 key 值）；当 insert 设置为 first/last 时，不能指定
    #     #     目标规则。
    #     #     """
    #     #     # print(post_param)
    #     #     if post_param['vendor'] == 'H3C':
    #     #         _res = SecPolicyMain.move_h3c_sec_policy(**post_param)
    #     #         if _res:
    #     #             return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #     #         return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     #     elif post_param['vendor'] == 'Huawei':
    #     #         if post_param['insert'] in ['first', 'last']:
    #     #             _res = HuaweiUsgSecPolicyConf.move(hostip=post_param['hostip'],
    #     #                                                rule_name=post_param['current_id'],
    #     #                                                insert=post_param['insert'])
    #     #             if _res:
    #     #                 return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #     #         else:
    #     #             _res = HuaweiUsgSecPolicyConf.move(hostip=post_param['hostip'],
    #     #                                                rule_name=post_param['current_id'],
    #     #                                                target_name=post_param['target_id'],
    #     #                                                insert=post_param['insert'])
    #     #             if _res:
    #     #                 return HttpResponse(json.dumps(dict(code=200)), content_type="application/json")
    #     #         return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     #     elif post_param['vendor'] == 'Hillstone':
    #     #         if post_param['insert'] in ['first', 'last']:
    #     #             path, fsm_res = HillstoneSecPolicyConf.move(hostip=post_param['hostip'],
    #     #                                                         current_id=post_param['current_id'],
    #     #                                                         insert=post_param['insert'])
    #     #         else:
    #     #             path, fsm_res = HillstoneSecPolicyConf.move(hostip=post_param['hostip'],
    #     #                                                         current_id=post_param['current_id'],
    #     #                                                         target_id=post_param['target_id'],
    #     #                                                         insert=post_param['insert'])
    #     #         if path:
    #     #             content = default_storage.open(path).read()
    #     #             return HttpResponse(json.dumps(dict(code=200, content=content, fsm_res=fsm_res), cls=DateEncoder),
    #     #                                 content_type="application/json")
    #     #         else:
    #     #             return HttpResponse(json.dumps(dict(code=400, content='', fsm_res=''), cls=DateEncoder),
    #     #                                 content_type="application/json")
    #     #     return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     # # 启用禁用策略 todo
    #     # if all(k in post_param for k in ("current_id", "enable", "vendor", "hostip")):
    #     #     print("post_param['enable']", post_param['enable'])
    #     #     if post_param['vendor'] == 'H3C':
    #     #         return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     #     elif post_param['vendor'] == 'Huawei':
    #     #         return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     #     elif post_param['vendor'] == 'Hillstone':
    #     #         path, fsm_res = HillstoneSecPolicyConf.on_off(hostip=post_param['hostip'],
    #     #                                                       current_id=post_param['current_id'],
    #     #                                                       enable=post_param['enable'])
    #     #         if path:
    #     #             content = default_storage.open(path).read()
    #     #             return HttpResponse(json.dumps(dict(code=200, content=content, fsm_res=fsm_res), cls=DateEncoder),
    #     #                                 content_type="application/json")
    #     #         else:
    #     #             return HttpResponse(json.dumps(dict(code=400, content='', fsm_res=''), cls=DateEncoder),
    #     #                                 content_type="application/json")
    #     #     return HttpResponse(json.dumps(dict(code=400)), content_type="application/json")
    #     # 定位IP归属策略
    #     if 'get_ip_owner' in post_param.keys():
    #         _ip = IPAddress(post_param['get_ip_owner'])
    #         params = {'or': [
    #             {'src_ip_split': {'$elemMatch': {'start': {'$gte': _ip.value}, 'end': {'$lte': _ip.value}}}},
    #             {'dst_ip_split': {'$elemMatch': {'start': {'$gte': _ip.value}, 'end': {'$lte': _ip.value}}}}
    #         ]}
    #         _res = sec_policy_mongo.find(query_dict=params,
    #                                                                  fileds={'_id': 0, 'src_ip_split': 0,
    #                                                                          'dstc_ip_split': 0})
    #         if _res:
    #             res = json.dumps({'results': _res, 'count': len(_res),
    #                               'code': 200})
    #             return HttpResponse(res, content_type="application/json")
    #         else:
    #             res = json.dumps({'results': [], 'count': 0,
    #                               'code': 400})
    #             return HttpResponse(res, content_type="application/json")
    #     print(request.META.get('CONTENT_TYPE'))
    #     print(request.user)
    #     remote_ip = request.META.get("REMOTE_ADDR")
    #     if request.user:
    #         user = UserProfile.objects.get(username=request.user)
    #         if user.has_perm('automation.change_autoflow'):
    #             # print(request.data)
    #             # jsondata = request.body.decode('utf-8')
    #             # print("jsondata", jsondata, type(jsondata))
    #             # post_param = json.loads(jsondata)
    #             post_param = request.data
    #             print("安全策略", post_param)
    #             # 更新单个设备安全策略信息(山石)
    #             if all(k in post_param for k in ("vendor", "update_device", "hostip")):
    #                 if post_param['vendor'] == 'Hillstone':
    #                     _res = SecPolicyMain.update_hillstone_addr_service(post_param['hostip'])
    #                     return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'result': 'OK'}),
    #                                         content_type="application/json")
    #                 return HttpResponse(json.dumps(dict(code=400, message='只有山石才需要异步更新信息')),
    #                                     content_type="application/json")
    #
    #             # 单个地址对象新增条目(新)
    #             if all(k in post_param for k in ("vendor", "hostip", "hostid")):
    #                 schema_res, msg = single_json_validate(post_param, sec_policy_schema)
    #                 print(schema_res)
    #                 # json数据验证通过
    #                 if schema_res:
    #                     post_param['user'] = str(request.user.username)
    #                     post_param['remote_ip'] = str(remote_ip)
    #                     res = config_sec_policy.apply_async(kwargs=post_param, queue=CELERY_QUEUE,
    #                                                         retry=True)  # config_backup
    #                     if str(res) == 'None':
    #                         print('forget')
    #                         res.forget()
    #                         return HttpResponse(json.dumps({'code': 400,
    #                                                         'message': '重复的任务参数', 'data': []}),
    #                                             content_type="application/json")
    #                     if res:
    #                         return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'data': str(res)}),
    #                                             content_type="application/json")
    #                 else:
    #                     return JsonResponse(msg, safe=False)
    #                 return HttpResponse(json.dumps(dict(code=400, message='操作不被允许', data=[])),
    #                                     content_type="application/json")
    #         else:
    #             return HttpResponse(json.dumps(dict(code=400, message='用户没有权限')), content_type="application/json")
    #     else:
    #         return HttpResponse(json.dumps(dict(code=400, message='没有获取到用户信息')), content_type="application/json")
    #
    #     return HttpResponse(json.dumps(dict(code=400, message='没有任何匹配')), content_type="application/json")
