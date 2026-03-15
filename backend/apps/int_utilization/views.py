import json
from datetime import datetime, timedelta
import django_filters
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework import filters
from .serializers import InterfaceUsedNewSerializer
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.network_analysis.models import InterfaceUtilizationSnapshot
from utils.db.mongo_ops import MongoOps
show_ip_mongo = MongoOps(db='Automation', coll='plan_ip_interface')
interface_mongo = MongoOps(db='Automation', coll='plan_interface_brief')


class InterfaceUsedFilter(django_filters.FilterSet):
    log_time = django_filters.CharFilter(field_name="snapshot_time", lookup_expr='icontains')
    host = django_filters.CharFilter(field_name="device_name", lookup_expr='icontains')
    host_ip = django_filters.CharFilter(field_name="manage_ip", lookup_expr='icontains')

    class Meta:
        model = InterfaceUtilizationSnapshot
        fields = ['manage_ip', 'device_name', 'device_serial_num', 'component_scope']


class InterfaceUsedNewViewSet(CustomViewBase):
    """
    接口利用率--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    http_method_names = ["get", "head", "options"]
    queryset = InterfaceUtilizationSnapshot.objects.all().order_by('-snapshot_time')
    serializer_class = InterfaceUsedNewSerializer
    pagination_class = LargeResultsSetPagination
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = InterfaceUsedFilter
    search_fields = ('manage_ip', 'device_name', 'component_name', 'device_serial_num')
    filter_fields = ('manage_ip', 'device_name')
    ordering_fields = ('snapshot_time', 'utilization_percent', 'manage_ip')

    def get_queryset(self):
        # 获取查询参数
        params = self.request.query_params
        start_time = params.get('start_time')
        end_time = params.get('end_time')
        time_unit = params.get('time_unit')
        time_num = params.get('time_num')
        range_time = params.get('range_time')

        # 处理开始和结束日期范围
        if start_time and end_time:
            start_dt = datetime.strptime(f"{start_time} 00:00:00", '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(f"{end_time} 23:59:59", '%Y-%m-%d %H:%M:%S')
            self.queryset = self.filter_by_date_range(start_dt, end_dt)

        # 处理时间单位和数值范围
        if time_unit and time_num:
            time_num = int(time_num)
            current_time = datetime.now()

            time_delta_map = {
                "days": lambda x: timedelta(days=x),
                "hours": lambda x: timedelta(hours=x),
                "minutes": lambda x: timedelta(minutes=x)
            }

            if time_unit in time_delta_map:
                start_time = current_time - time_delta_map[time_unit](time_num)
                self.queryset = self.filter_by_date_range(start_time, current_time)

        # 处理时间戳范围
        if range_time is not None:
            dt_object = datetime.fromtimestamp(int(int(range_time) / 1000))
            start_dt = datetime.strptime(dt_object.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.strptime(dt_object.strftime('%Y-%m-%d ') + "23:59:59", '%Y-%m-%d %H:%M:%S')
            self.queryset = self.filter_by_date_range(start_dt, end_dt)

        return self.queryset

    def filter_by_date_range(self, start_dt, end_dt):
        return self.queryset.filter(snapshot_time__range=(start_dt, end_dt))

class InterfaceView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        if get_param.get('get_interface_by_hostip'):
            hostip = get_param['get_interface_by_hostip']
            layer3interface_res = show_ip_mongo.find(query_dict={'hostip': hostip},
                                                     fields={'interface': 1, 'line_status': 1, '_id': 0})
            layer2interface_res = interface_mongo.find(query_dict={'hostip': hostip},
                                                       fields={'interface': 1, 'status': 1, '_id': 0})

            combined_interfaces = {x['interface']: {'status': x['line_status'].upper()} for x in layer3interface_res}
            for x in layer2interface_res:
                if x['interface'] not in combined_interfaces or not combined_interfaces[x['interface']]['status']:
                    combined_interfaces[x['interface']] = {'status': x['status'].upper()}
            tmp_res = [{'name': name, 'status': data['status']} for name, data in combined_interfaces.items()]
            res = {}
            try:
                # 判断堆叠
                for i in tmp_res:
                    if i['name'].startswith('lo'):
                        continue
                    elif i['name'].startswith('mgmt'):
                        continue
                    elif i['name'].startswith('M-GigabitEthernet'):
                        continue
                    elif i['name'].startswith('AggregatePort'):
                        continue
                    elif i['name'].startswith('LoopBack'):
                        continue
                    elif i['name'].startswith('Vlan-interface'):
                        continue
                    elif i['name'].startswith('Route'):
                        continue
                    elif i['name'].startswith('Vsi'):
                        continue
                    elif i['name'].startswith('MEth'):
                        continue
                    _tmp_slot = i['name'].split('/')[0]
                    i['index'] = int(i['name'].split('/')[-1])
                    i['speed'] = str(i['name'].split('/')[0][:-1])
                    if str(_tmp_slot[-1]) in res.keys():
                        if i['speed'] in res[str(_tmp_slot[-1])].keys():
                            res[str(_tmp_slot[-1])][i['speed']].append(i)
                        else:
                            res[str(_tmp_slot[-1])][i['speed']] = [i]
                    else:
                        res[str(_tmp_slot[-1])] = {}
                        res[str(_tmp_slot[-1])][i['speed']] = [i]
                # res = [x for x in tmp_res if x['status'] in ["UP", "DOWN"]]
                for slot in res.keys():  # slot
                    y_list = [i for i in range(1, len(res[slot].keys()) + 1)]  # 端口类型分类
                    for k, _y in zip(res[slot].keys(), y_list):
                        y = 100
                        if len(res[slot][k]) <= 24:  # 如果Ten-GigabitEthernet接口类型的数量小于24个，就直接第一行排列
                            x = 100
                            for interface in res[slot][k]:  # 接口前缀
                                interface['y'] = y
                                interface['x'] = x
                                x += 50
                        elif len(res[slot][k]) > 24:  # 如果接口类型数量超过24个，就要分两行显示，通过控制Y的值来分行
                            x = 100
                            for interface in res[slot][k]:  # 接口前缀
                                if interface['index'] <= 24:
                                    interface['y'] = y
                                    interface['x'] = x
                                    x += 50
                            x = 100
                            for interface in res[slot][k]:  # 接口前缀
                                if interface['index'] > 24:
                                    interface['y'] = y + 75
                                    interface['x'] = x
                                    x += 50
                result = {
                    "code": 200,
                    "count": len(res),
                    "message": "成功",
                    "results": res
                }
                return JsonResponse(result, safe=False)
            except Exception as e:
                result = {
                    "code": 200,
                    "count": 0,
                    "message": str(e),
                    "results": res
                }
                return JsonResponse(result, safe=False)


class BaseInterfacePortView(APIView):
    # 接口和端口的基础接口视图
    def get_common_response(self, get_param, mongo_collection, query_mapping):
        if not all(k in get_param for k in ("page_size", "page", "host_ip")):
            return JsonResponse({"code": 200, "msg": "success", "data": [], "count": 0}, safe=True)

        _params = json.loads(get_param["query"])
        query = {"hostip": get_param["host_ip"]}

        _query = {k: v for k, v in _params.items() if v}
        for param_key, query_key in query_mapping.items():
            if param_key in _query:
                query[query_key] = _query[param_key]

        res = mongo_collection.find_page_query(
            query_dict=query,
            fields={'_id': 0},
            page_size=int(get_param['page_size']),
            page_num=int(get_param['page'])
        )
        count = mongo_collection.count_documents(query=query)

        return JsonResponse({
            'code': 200,
            'msg': 'success',
            'data': res,
            'count': count
        }, safe=True)


class PortUsedView(BaseInterfacePortView):
    # 端口视图接口
    def get(self, request):
        query_mapping = {
            'interface': 'interface',
            'up': 'up',
            'speed': 'speed',
            'duplex': 'duplex'
        }
        return self.get_common_response(
            request.GET.dict(),
            interface_mongo,
            query_mapping
        )


class InterfaceUsedV2View(BaseInterfacePortView):
    # 接口视图
    def get(self, request):
        query_mapping = {
            'interface': 'interface',
            'line_status': 'line_status',
            'protocol_status': 'protocol_status',
            'ipaddress': 'ipaddress',
            'ipmask': 'ipmask'
        }
        return self.get_common_response(
            request.GET.dict(),
            show_ip_mongo,
            query_mapping
        )
