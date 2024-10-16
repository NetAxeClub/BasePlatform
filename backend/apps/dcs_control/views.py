import json
from rest_framework.views import APIView
from django.http import JsonResponse, HttpResponse
from netaxe.settings import DEBUG
from apps.asset.models import AssetIpInfo
from apps.dcs_control.tasks import FirewallMain, SecPolicyMain
from utils.db.mongo_ops import MongoNetOps, MongoOps
from apps.dcs_control.jsonschema import single_json_validate
from apps.dcs_control.json_validate.deny_by_addr_obj import deny_schema
from apps.dcs_control.json_validate.address_schema import address_schema
from apps.dcs_control.tasks import bulk_deny_by_address, address_set

if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config'


# 一键封堵
class DenyByAddrObj(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        # 查询策略包含指定的地址对象的策略匹配次数
        if all(k in get_param for k in ("vendor", "hostip", "address_book")):
            if get_param['vendor'] in ['hillstone', 'h3c', 'huawei']:
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
                return JsonResponse({'code': 400, 'msg': 'vendor 必须是 hillstone  h3c  huawei 其中一个'})

    def post(self, request):
        # print(request.META.get('CONTENT_TYPE'))
        # print(request.user)
        post_param = request.data
        # if post_param.get('user'):
        user = '临时用户'
        # 一键封堵操作
        schema_res, msg = single_json_validate(post_param, deny_schema)
        # json数据验证通过
        if schema_res:
            post_param['origin'] = "DCS控制器"
            post_param['user'] = "临时用户"
            post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
            print('CELERY_QUEUE', CELERY_QUEUE)
            res = bulk_deny_by_address.apply_async(kwargs=post_param, queue=CELERY_QUEUE)  # config_backup
            if str(res) == 'None':
                print('forget')
                res.forget()
                return JsonResponse({'code': 400, 'message': 'duplicate task execution', 'data': []})
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
        # print(get_param)
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
                _res = MongoOps(db='Automation', coll='hillstone_address') \
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
        print("地址组", post_param)
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
                                                    'message': 'duplicate task execution', 'data': []}),
                                        content_type="application/json")
                if res:
                    return HttpResponse(json.dumps({'code': 200, 'message': 'OK', 'data': str(res)}),
                                        content_type="application/json")
            else:
                return JsonResponse(msg, safe=False)
            return HttpResponse(json.dumps(dict(code=400, message='操作不被允许', data=[])),
                                content_type="application/json")

        return JsonResponse(dict(code=400, message='没有任何匹配'))