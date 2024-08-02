import json
from rest_framework.views import APIView
from django.http import JsonResponse
from netaxe.settings import DEBUG
from apps.asset.models import AssetIpInfo
from utils.db.mongo_ops import MongoNetOps
from .jsonschema import single_json_validate
from .json_validate.deny_by_addr_obj import deny_schema
from .tasks import bulk_deny_by_address

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
            post_param['remote_ip'] = str(request.META.get("REMOTE_ADDR"))
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
