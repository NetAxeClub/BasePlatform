import json
import operator
import os
import time
from datetime import date
import django_filters
from django.core.cache import cache
from django.db.models import Count
from django.views import View
from django.http import JsonResponse, FileResponse, Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework import filters

from .json_validate.address_schema import address_schema
from .json_validate.dnat_schema import post_dnat_schema
from .json_validate.service_schema import service_schema
# from .json_validate import address_schema
from .jsonschema import single_json_validate
from apps.automation.tasks import interface_used
from netaxe.settings import MEDIA_ROOT, DEBUG
from utils.crypt_pwd import CryptPwd
from apps.api.tools.custom_pagination import LargeResultsSetPagination
from apps.api.tools.custom_viewset_base import CustomViewBase
from apps.asset.models import Idc, AssetAccount, Vendor, Role, Category, Model, Attribute, Framework, NetworkDevice, \
    IdcModel, NetZone, Rack, AdminRecord, Server, ServerModel, ContainerService, ServerVendor, ServerAccount
from apps.asset.serializers import IdcSerializer, AssetAccountSerializer, AssetVendorSerializer, RoleSerializer, \
    CategorySerializer, ModelSerializer, AttributeSerializer, FrameworkSerializer, NetworkDeviceSerializer, \
    IdcModelSerializer, NetZoneSerializer, CmdbRackSerializer, AdminRecordSerializer, ServerSerializer, \
    ServerModelSerializer, ContainerServiceSerializer, ServerVendorSerializer, ServerAccountSerializer
from utils.cmdb_import import search_cmdb_vendor_id, search_cmdb_idc_id, search_cmdb_netzone_id, search_cmdb_role_id, \
    search_cmdb_idc_model_id, search_cmdb_cabinet_id, search_cmdb_category_id, search_cmdb_attribute_id, \
    search_cmdb_framework_id, returndate, csv_device_staus, pandas_read_file, old_import_parse
from utils.db.mongo_ops import MongoNetOps, MongoOps
from ..users.models import UserProfile

if DEBUG:
    CELERY_QUEUE = 'dev'
else:
    CELERY_QUEUE = 'config_backup'


class ResourceManageExcelView(APIView):
    permission_classes = (AllowAny,)
    # permission_classes = ()
    authentication_classes = ()

    def post(self, request):
        file = request.FILES.get('file')
        # 获取文件位置
        filename = os.path.join(MEDIA_ROOT, 'upload', file.name)
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        with open(filename, 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        # pandas文件内容解析
        import_content_df = pandas_read_file(filename)
        # print(import_content_df)
        import_list = []
        for i in import_content_df.values:
            import_list.append(i.tolist())

        import_success_list, import_exists_list, import_fail_list, detail = old_import_parse(import_list)
        # print(import_success_list, import_exists_list, import_fail_list)
        try:
            if len(import_success_list) == len(import_list):
                return JsonResponse({'code': 200, 'msg': '全部导入成功！'})
            if import_exists_list:
                return JsonResponse({'code': 400, 'msg': '导入失败！当前导入SN设备已存在,请校验导入数据'})
            if import_fail_list:
                error_msg = ''.join([i[0] + i['import_fail_reason'] for i in import_fail_list])
                return JsonResponse({'code': 400, 'msg': '导入失败！请校验导入数据' + error_msg})
            if detail == 'success':
                return JsonResponse({'code': 200, 'msg': '导入成功！' + str(detail)})
            else:
                return JsonResponse({'code': 400, 'msg': '导入失败！' + str(detail)})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': '导入失败！{}'.format(e)})

    def get(self, request):
        try:
            file_path = os.path.join(MEDIA_ROOT, 'cmdbExcelTemplate/import-demo.xlsx')
            response = FileResponse((open(file_path, 'rb')))
            response['Content-Type'] = 'application/octet-stream'
            response['Content-Disposition'] = 'attachment;filename="import-demo.xlsx"'
            response["Access-Control-Allow-Methods"] = "*"
            response["Access-Control-Allow-Credentials"] = True
            response['Access-Control-Allow-Headers'] = "Authorization"
            response["Access-Control-Allow-Origin"] = "/".join(request.META.get("HTTP_REFERER").split("/")[0:3])
            return response
        except Exception:
            raise Http404


class DeviceAccountView(APIView):
    def post(self, request):
        post_params = request.POST.dict()
        device = NetworkDevice.objects.get(id=post_params['asset_id'])
        account_list = json.loads(post_params['account'])
        device.account.set(account_list)
        return JsonResponse({'code': 200, 'message': '关联管理账户成功'})

    def get(self, request):
        get_params = request.GET.dict()
        device = NetworkDevice.objects.get(serial_num=get_params['serial_num'])
        account_query = device.account.all()
        serializer_data = AssetAccountSerializer(account_query, many=True)
        account_list = []
        _CryptPwd = CryptPwd()
        for i in serializer_data.data:
            account_dict = {
                'name': i['name'],
                'username': i['username'],
                'protocol': i['protocol'],
                'port': i['port'],
                'password': _CryptPwd.decrypt_pwd(i['password'])
            }
            account_list.append(account_dict)
        # serializer_data = AssetAccountSerializer(account_query, many=True)

        return JsonResponse({'code': 200, 'message': '获取账户信息成功', 'results': account_list})


class CmdbChart(APIView):
    permission_classes = ()
    authentication_classes = ()

    def get(self, request):
        get_params = request.GET.dict()
        # 设备登录日志
        if 'login_record' in get_params:
            login_record_list = []
            login_record_queryset = AdminRecord.objects.values('admin_login_user').annotate(
                sum_count=Count('admin_login_user'))
            for i in login_record_queryset:
                i['admin_login_user_name'] = i['admin_login_user']
                login_record_list.append(i)
            # # 倒序--选择前5条作为TOP5
            sorted_login_record_list = sorted(login_record_list, key=operator.itemgetter('sum_count'), reverse=True)
            result = {
                "code": 200,
                "data": sorted_login_record_list[0:7]
            }
            return JsonResponse(result, safe=False)
        # 设备类型分类
        if 'cmdb_category' in get_params:
            # RES = NetworkDevice.objects.values('category__name').annotate(sum_count=Count('category'))
            cmdb_category_list = []
            cmdb_category_queryset = NetworkDevice.objects.values('category__name').annotate(
                sum_count=Count('category'))
            for i in cmdb_category_queryset:
                # i['admin_login_user_name'] = UserProfile.objects.filter(id=i['admin_login_user'])[0].username
                cmdb_category_list.append(i)
            # # # 倒序--选择前5条作为TOP5
            # sorted_cmdb_category_list = sorted(cmdb_category_list, key=operator.itemgetter('sum_count'), reverse=True)
            result = {
                "code": 200,
                "data": cmdb_category_list
            }
            return JsonResponse(result, safe=False)
        # 设备维保日期
        if 'cmdb_expire' in get_params:
            today_time = time.strftime('%Y-%m-%d', time.localtime())
            expire_list = []
            expire_queryset = NetworkDevice.objects.filter(expire__lt=today_time)
            total_device_queryset = NetworkDevice.objects.all()
            result = {
                "code": 200,
                "data": {
                    'expire_count': len(expire_queryset),
                    'total_count': len(total_device_queryset)
                }
            }
            return JsonResponse(result, safe=False)
        # 获取设备类型-生产或研测等等
        if 'network_type' in get_params:
            RtQuery = NetworkDevice.objects.filter(name__contains='RT')
            RdQuery = NetworkDevice.objects.filter(name__contains='RD')
            PoQuery = NetworkDevice.objects.filter(name__contains='PO')
            MgQuery = NetworkDevice.objects.filter(name__contains='MG')
            result = {
                "code": 200,
                "data": [
                    {'name': "研测网络", 'value': len(RtQuery)},
                    {'name': "研发网络", 'value': len(RdQuery)},
                    {'name': "生产网络", 'value': len(PoQuery)},
                    {'name': "管理网络", 'value': len(MgQuery)},
                ]
            }
            return JsonResponse(result, safe=False)
        # 仅统计8:30-17:30算工作时间暂无法统计法定工作日数据 TODO
        if 'cmdb_login_time' in get_params:
            login_time_list = []
            work_time_list = []
            login_record_queryset = AdminRecord.objects.values().all()
            for i in login_record_queryset:
                current_day = i['admin_start_time'][0:11]
                if current_day + '08:30' < i['admin_start_time'] < current_day + "17:30":
                    work_time_list.append(i)
            result = {
                'code': 200,
                'data': {
                    'work_time_count': len(work_time_list),
                    'total_time_count': len(login_record_queryset),
                    'not_work_time': len(login_record_queryset) - len(work_time_list)
                }
            }
            return JsonResponse(result, safe=False)

        # 获取最近一次接口利用率信息
        if all(k in get_params for k in ("interface_used", "token", "bgbu")):
            bgbu_int = json.loads(get_params['bgbu'])
            bgbu_list = [int(x) for x in bgbu_int]
            res, total, unused_list, total_count_list, category_list = interface_used(bgbu_list)
            if res:
                res = json.dumps({'code': 200, 'used': res, 'total': total, 'total_count_list': total_count_list,
                                  'unused_list': unused_list,
                                  'category_list': category_list})
            else:
                res = json.dumps({'code': 400, 'used': [], 'total': 0, 'unused_list': [], 'total_count_list': [],
                                  'category_list': []})
            return HttpResponse(res, content_type="application/json")


# asset IDC
class IdcViewSet(CustomViewBase):
    """
    IDC 处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Idc.objects.all().order_by('-id')
    serializer_class = IdcSerializer
    permission_classes = ()
    authentication_classes = ()
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    # 设置搜索的关键字
    search_fields = '__all__'


class CmdbNetzoneModelViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = NetZone.objects.all().order_by('-id')
    serializer_class = NetZoneSerializer
    permission_classes = ()
    authentication_classes = ()
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    # 设置搜索的关键字
    search_fields = '__all__'


class CmdbRackModelViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Rack.objects.all().order_by('id')
    # queryset = NetZoneSerializer.setup_eager_loading(queryset)
    serializer_class = CmdbRackSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    permission_classes = ()
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'


class CmdbIdcModelViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = IdcModel.objects.all().order_by('id')
    queryset = IdcModelSerializer.setup_eager_loading(queryset)
    serializer_class = IdcModelSerializer
    # permission_classes = (permissions.IsAuthenticated,)
    permission_classes = ()
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'


# asset account
class AccountList(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = AssetAccount.objects.all().order_by('id')
    serializer_class = AssetAccountSerializer
    pagination_class = LargeResultsSetPagination
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    # 设置搜索的关键字
    search_fields = '__all__'
    # list_cache_key_func = QueryParamsKeyConstructor()


class ServerAccountList(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ServerAccount.objects.all().order_by('id')
    serializer_class = ServerAccountSerializer
    pagination_class = LargeResultsSetPagination
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    # 设置搜索的关键字
    search_fields = '__all__'
    # list_cache_key_func = QueryParamsKeyConstructor()


class ServerVendorList(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ServerVendor.objects.all().order_by('id')
    serializer_class = ServerVendorSerializer
    pagination_class = LargeResultsSetPagination
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    # 设置搜索的关键字
    search_fields = '__all__'
    # list_cache_key_func = QueryParamsKeyConstructor()


# asset vendor
class VendorViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Vendor.objects.all().order_by('id')
    serializer_class = AssetVendorSerializer
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'


# asset role
class AssetRoleViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Role.objects.all().order_by('id')
    serializer_class = RoleSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'


class CategoryViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Category.objects.all().order_by('id')
    serializer_class = CategorySerializer
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'


class ModelViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Model.objects.all().order_by('id')
    queryset = ModelSerializer.setup_eager_loading(queryset)
    serializer_class = ModelSerializer
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('vendor', 'name')
    pagination_class = LargeResultsSetPagination


class AttributelViewSet(CustomViewBase):
    """
    处理 设备网络属性 GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Attribute.objects.all().order_by('id')
    serializer_class = AttributeSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination


class FrameworkViewSet(CustomViewBase):
    """
    处理 设备网络架构 GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Framework.objects.all().order_by('id')
    serializer_class = FrameworkSerializer
    authentication_classes = ()
    permission_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination


class NetworkDeviceFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    serial_num = django_filters.CharFilter(lookup_expr='icontains')
    manage_ip = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = NetworkDevice
        fields = '__all__'


class NetworkDeviceViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = NetworkDevice.objects.all().order_by('-id')
    queryset = NetworkDeviceSerializer.setup_eager_loading(queryset)
    serializer_class = NetworkDeviceSerializer
    # authentication_classes = (authentication.JWTAuthentication,)
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = NetworkDeviceFilter
    filter_fields = ('serial_num', 'manage_ip', 'bridge_mac', 'category__name',
                     'name', 'vendor__name', 'idc__name', 'patch_version', 'soft_version',
                     'model__name', 'memo', 'status', 'ha_status')
    # pagination_class = LimitSet
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = ('serial_num', 'manage_ip', 'bridge_mac', 'category__name',
                     'name', 'vendor__name', 'idc__name', 'patch_version', 'soft_version',
                     'model__name', 'memo', 'status', 'ha_status')

    def get_queryset(self):
        """
        expires  比 expire多一个s ，用来筛选已过期的设备数据 lt 小于  gt 大于  lte小于等于  gte 大于等于
        :return:
        """
        expires = self.request.query_params.get('expires', None)
        search_host_list = self.request.query_params.get('search_host_list', None)
        if search_host_list:
            if search_host_list.find('-') != -1:
                return self.queryset.filter(manage_ip__in=search_host_list.split('-'))
            else:
                return self.queryset.filter(manage_ip__in=[search_host_list])
            # return self.queryset.filter(manage_ip__in=search_host_list)
        if expires == '1':
            return self.queryset.filter(expire__lt=date.today())
        elif expires == '0':
            return self.queryset.filter(expire__gt=date.today())
        else:
            return self.queryset

    # 重新update方法主要用来捕获更改前的字段值并赋值给self.log
    # def update(self, request, *args, **kwargs):
    #     print('更新', super().update(request, *args, **kwargs))
    #     return super().update(request, *args, **kwargs)


class ServerFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    serial_num = django_filters.CharFilter(lookup_expr='icontains')
    manage_ip = django_filters.CharFilter(lookup_expr='icontains')
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Server
        fields = '__all__'


class ServerDeviceViewSet(CustomViewBase):
    """
    处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = Server.objects.all().order_by('id')
    queryset = ServerSerializer.setup_eager_loading(queryset)
    serializer_class = ServerSerializer

    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = ServerFilter
    filter_fields = '__all__'
    permission_classes = ()
    authentication_classes = ()
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = ("cpu_model", "name", "manager_name", "vendor__name", "manage_ip")


class ServerModelViewSet(CustomViewBase):
    """
    处理 服务器硬件型号 GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ServerModel.objects.all().order_by('id')
    queryset = ServerModelSerializer.setup_eager_loading(queryset)
    serializer_class = ServerModelSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = NetworkDeviceFilter
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'
    # list_cache_key_func = QueryParamsKeyConstructor()


class ContainerServiceViewSet(CustomViewBase):
    """
    处理 容器微服务 GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ContainerService.objects.all().order_by('id')
    serializer_class = ContainerServiceSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = NetworkDeviceFilter
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'


class ServerVendorViewSet(CustomViewBase):
    """
    处理 服务器资产 GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = ServerVendor.objects.all().order_by('id')
    serializer_class = ServerVendorSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # filterset_class = NetworkDeviceFilter
    filter_fields = '__all__'
    pagination_class = LargeResultsSetPagination
    # 设置搜索的关键字
    search_fields = '__all__'
    # list_cache_key_func = QueryParamsKeyConstructor()


# webssh登录日志 模糊字段过滤器
class AdminRecordFilter(django_filters.FilterSet):
    """模糊字段过滤"""

    admin_start_time = django_filters.CharFilter(lookup_expr='icontains')

    # host__idc = django_filters.CharFilter()
    # host__name = django_filters.CharFilter(lookup_expr='icontains')
    # host__manage_ip = django_filters.CharFilter(lookup_expr='icontains')
    # host__manage_ip = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = AdminRecord
        fields = '__all__'


# webssh登录日志
class AdminRecordViewSet(CustomViewBase):
    """
    webssh登录日志---处理  GET POST , 处理 /api/post/<pk>/ GET PUT PATCH DELETE
    """
    queryset = AdminRecord.objects.all().order_by('-id')
    queryset = AdminRecordSerializer.setup_eager_loading(queryset)
    serializer_class = AdminRecordSerializer
    permission_classes = ()
    authentication_classes = ()
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    # 如果要允许对某些字段进行过滤，可以使用filter_fields属性。
    filterset_class = AdminRecordFilter
    filter_fields = '__all__'
    search_fields = '__all__'
    ordering_fields = '__all__'

    def get_queryset(self):
        start = self.request.query_params.get('start_time', None)
        end = self.request.query_params.get('end_time', None)
        if start and end:
            return AdminRecord.objects.select_related('admin_login_user').filter(
                admin_start_time__gt=start,
                admin_start_time__lt=end)
        return AdminRecord.objects.all()
