import django_filters
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from rest_framework import viewsets, permissions, filters, pagination
from .models import InterfaceUsed
from .serializers import InterfaceUsedNewSerializer
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from utils.db.mongo_ops import MongoOps
show_ip_mongo = MongoOps(db='Automation', coll='layer3interface')
interface_mongo = MongoOps(db='Automation', coll='layer2interface')


class InterfaceUsedFilter(django_filters.FilterSet):
    log_time = django_filters.CharFilter(lookup_expr='icontains')
    host = django_filters.CharFilter(lookup_expr='icontains')
    host_ip = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = InterfaceUsed
        fields = '__all__'


class InterfaceUsedNewViewSet(CustomViewBase):
    """
    接口利用率--处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = InterfaceUsed.objects.all().order_by('-log_time')
    # queryset = InterfaceUsedNewSerializer.setup_eager_loading(queryset)
    serializer_class = InterfaceUsedNewSerializer
    # permission_classes = ()
    # authentication_classes = ()
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    # filterset_class = InterfaceUsedFilter
    search_fields = ('host_ip', 'host')
    filter_fields = ('host_ip', 'host')
    ordering_fields = ('log_time', 'id')

    def get_queryset(self):
        start = self.request.query_params.get('start_time', None)
        end = self.request.query_params.get('end_time', None)
        host_id = self.request.query_params.get('host_id', None)
        interface_used = self.request.query_params.get('interface_used', None)
        if start and end:
            return self.queryset.filter(log_time__range=(start, end))

        if host_id and interface_used:
            return self.queryset.filter(host_id=host_id)
        return self.queryset


class InterfaceView(APIView):
    def get(self, request):
        get_param = request.GET.dict()
        if get_param.get('get_interface_by_hostip'):
            hostip = get_param['get_interface_by_hostip']
            layer3interface_res = show_ip_mongo.find(query_dict={'hostip': hostip},
                                                     fileds={'interface': 1, 'line_status': 1, '_id': 0})
            layer2interface_res = interface_mongo.find(query_dict={'hostip': hostip},
                                                       fileds={'interface': 1, 'status': 1, '_id': 0})
            tmp_res = [
                         {'name': x['interface'], 'status': x['line_status'].upper()} for x in layer3interface_res if layer3interface_res
                     ] + [
                {'name': x['interface'], 'status': x['status'].upper()} for x in layer2interface_res if layer2interface_res
            ]
            res = {}
            try:
            # 判断堆叠
                for i in tmp_res:
                    if i['name'].startswith('lo'):
                        continue
                    elif i['name'].startswith('mgmt'):
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
                    _tmp_slot = i['name'].split('/')[0]
                    i['index'] = int(i['name'].split('/')[-1])
                    if str(_tmp_slot[-1]) in res.keys():
                        res[str(_tmp_slot[-1])].append(i)
                    else:
                        res[str(_tmp_slot[-1])] = [i]
                # res = [x for x in tmp_res if x['status'] in ["UP", "DOWN"]]

                for k, v in res.items():
                    x = 100
                    for _v in v:
                        if _v['index'] <= len(v) / 2:
                            _v['y'] = 100
                            _v['x'] = x
                            x += 50
                for k, v in res.items():
                    x = 100
                    for _v in v:
                        if _v['index'] > len(v) / 2:
                            _v['y'] = 200
                            _v['x'] = x
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