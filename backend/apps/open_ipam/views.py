import asyncio
import json
import threading
import time
from datetime import datetime, timedelta

from django.db.models import Count
# from asgiref.sync import sync_to_async, async_to_sync
# from django.db.models import Count
# from django.db.models import Count, Sum
# from django.db.models.query import RawQuerySet
from django.http import JsonResponse, HttpResponse
# from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
from netaddr import iter_iprange
from rest_framework import serializers, filters
from django.utils.translation import gettext_lazy as _
# from rest_framework.authentication import SessionAuthentication
# from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import ListAPIView, get_object_or_404, RetrieveAPIView
# from rest_framework.permissions import DjangoModelPermissions
# from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Subnet, IpAddress, TagsModel
from .serializers import HostsResponseSerializer, SubnetSerializer, IpAddressSerializer, \
    TagsModelSerializer
# TagCountSerializer
from utils.ipam_pagenations import HostsListPagination
from utils.ipam_utils import IpAmForNetwork
import ipaddr

from utils.custom.pagination import LargeResultsSetPagination
from utils.custom.viewset import CustomViewBase


# 定义host 响应 返回值字段
class HostsResponse(object):
    def __init__(self, address, used, tag, subnet, lastOnlineTime, description):
        # def __init__(self, address, used, tag, subnet):
        self.address = address
        self.used = used
        self.tag = tag
        self.subnet = subnet
        self.lastOnlineTime = lastOnlineTime
        self.description = description


class HostsSet:
    model = Subnet

    def __init__(self, subnet, start=0, stop=None):
        self.start = start
        self.stop = stop
        self.subnet = subnet
        self.network = int(self.subnet.subnet.network_address)
        self.used_set = subnet.ipaddress_set.all()

    def __getitem__(self, i):
        # 如果传递进来的参数i是一个切片对象，则获取start和stop的值
        if isinstance(i, slice):
            start = i.start
            stop = i.stop
            # 如果 start 或 stop 是 None，说明切片的开始或结束位置没有被指定，那么就将其赋值为 0 或 self.count()
            if start is None:  # pragma: no cover
                start = 0
            if stop is None:  # pragma: no cover
                stop = self.count()
            # 如果 stop 的值超过了索引的范围，那么就将其赋值为 self.count()。
            else:
                stop = min(stop, self.count())
            return HostsSet(self.subnet, self.start + start, self.start + stop)
        # 如果索引超出count 则报index错
        if i >= self.count():
            raise IndexError
        # Host starts from next address生成一个 IP 地址对象

        ip_address_instance = self.subnet.subnet._address_class(self.network + 1 + i + self.start)
        # print()
        # In case of single hosts ie subnet/32 & /128
        if self.subnet.subnet.prefixlen in [32, 128]:
            ip_address_instance = ip_address_instance - 1
        # 判断Ip地址是否存在，编辑使用与否
        used = self.used_set.filter(ip_address=str(ip_address_instance)).exists()
        # 默认tag为1
        tag = 1

        host_instance = self.used_set.filter(ip_address=str(ip_address_instance)).first()
        # 如果已经被使用，需要判断实际的tag是什么
        if used:
            tag = host_instance.tag
        # 描述和最近在线时间

        description = ''
        lastOnlineTime = ''

        if host_instance:
            description = host_instance.description
            lastOnlineTime = host_instance.lastOnlineTime

        return HostsResponse(str(ip_address_instance), used, tag, self.subnet, lastOnlineTime, description)

    # 计算当前subnet的实际可用地址是多少
    def count(self):
        if self.stop is not None:
            return self.stop - self.start
        broadcast = int(self.subnet.subnet.broadcast_address)

        # IPV4
        if self.subnet.subnet.version == 4:
            # Networks with a mask of 32 will return a list
            # containing the single host address
            if self.subnet.subnet.prefixlen == 32:
                return 1
            # Other than subnet /32, exclude broadcast
            return broadcast - self.network - 1
        # IPV6
        else:
            # Subnet/128 only contains single host address
            if self.subnet.subnet.prefixlen == 128:
                return 1
            return broadcast - self.network

    def __len__(self):
        return self.count()

    def index_of(self, address):
        index = int(self.subnet.subnet._address_class(address)) - self.network - 1
        if index < 0 or index >= self.count():  # pragma: no cover
            raise serializers.ValidationError({'detail': _('Invalid Address')})
        return index


# class ProtectedAPIMixin(object):
#     authentication_classes = [SessionAuthentication]
#     permission_classes = [DjangoModelPermissions]
#     throttle_scope = 'ipam'

# ProtectedAPIMixin
# class SubnetHostsView(ListAPIView):
#     subnet_model = Subnet
#     queryset = Subnet.objects.none()
#     serializer_class = HostsResponseSerializer
#     pagination_class = HostsListPagination
#
#     def get_queryset(self):
#         super().get_queryset()
#         # get subnet instance
#         subnet = get_object_or_404(self.subnet_model, pk=self.kwargs['subnet_id'])
#         queryset = HostsSet(subnet)
#         return queryset


# 获取可用I配置
# class AvailableIpView(RetrieveAPIView):
#     subnet_model = Subnet
#     queryset = IpAddress.objects.none()
#     serializer_class = serializers.Serializer
#
#     def get(self, request, *args, **kwargs):
#         subnet = get_object_or_404(self.subnet_model, pk=self.kwargs['subnet_id'])
#         print(subnet)
#         return Response(subnet.get_next_available_ip())


# 子网网段API
class SubnetApiViewSet(CustomViewBase):
    # subnet_model = Subnet
    permission_classes = ()
    queryset = Subnet.objects.all().order_by('-id')
    serializer_class = SubnetSerializer
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = ('mask', 'name')


# IP地址Api
class IpAddressApiViewSet(CustomViewBase):
    # subnet_model = Subnet
    # permission_classes = ()
    queryset = IpAddress.objects.all().order_by('-id')
    serializer_class = IpAddressSerializer
    pagination_class = LargeResultsSetPagination
    # 配置搜索功能
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filter_fields = '__all__'


class SubnetAddressView(ListAPIView):
    subnet_model = Subnet
    queryset = Subnet.objects.none()
    serializer_class = HostsResponseSerializer
    pagination_class = HostsListPagination

    def get_queryset(self):
        # start_time = time.time() * 1000
        super().get_queryset()
        subnet_instance = Subnet.objects.get(id=self.kwargs['subnet_id'])
        queryset = HostsSet(subnet_instance)
        return queryset


class IpAmAddressTagGroupView(APIView):
    def get(self, request):
        try:
            # sql = "SELECT 1 as id ,tag, COUNT(*) as count FROM ipam_ip_address GROUP BY tag"
            # raw_queryset: RawQuerySet = IpAddress.objects.raw(sql, translations={})
            # print(raw_queryset)
            # # 序列化查询结果
            # serializer = TagCountSerializer(raw_queryset, many=True)
            tag_counts = IpAddress.objects.values('tag').annotate(count=Count('id')).order_by('tag')
            print("tag_counts",tag_counts)
            # 返回JSON响应
            res = {'data': list(tag_counts), 'code': 200, 'message': 'success'}
            return JsonResponse(res, safe=True)  #
        except Exception as e:
            # 其他异常返回500错误
            res = {'data': [], 'code': 500, 'message': str(e)}
            return JsonResponse(res, safe=True)


# 获取 get subnet_tree
class IpAmSubnetTreeView(APIView):
    def get(self, request):
        get_params = request.GET.dict()
        # print(get_params)
        if 'subnet' in get_params:
            ip_am_network = IpAmForNetwork()
            res_list = list(Subnet.objects.all().order_by('subnet').values())
            # 处理树结构返回前端
            tree = ip_am_network.generate_netops_tree(res_list)
            res = {'data': tree, 'code': 200, }
            return JsonResponse(res, safe=True)
        if "tags" in get_params:
            tag_choices = TagsModel.objects.all()
            tags = TagsModelSerializer(tag_choices, many=True)
            res = {'data': tags.data, 'code': 200, 'count': len(tags.data)}
            return JsonResponse(res, safe=True)
        # 获取导出网段
        else:
            tmp = Subnet.objects.all().order_by('subnet')
            tmp_serializer = SubnetSerializer(tmp, many=True)
            # download_res_list = sorted(tmp_serializer, key=lambda e: e['id'], reverse=False)
            # print(download_res_list)
            res = {'data': tmp_serializer.data, 'code': 200, 'count': len(tmp_serializer.data)}
            return JsonResponse(res, safe=True)

        # return HttpResponse("ok")


# 地址操作 增删改查
class IpAmHandelView(APIView):
    def post(self, request):
        print("request", json.loads(request.body))
        request_data = json.loads(request.body)
        update = request_data.get('update')
        range_update = request_data.get('range_update')
        delete = request_data.get('delete')
        subnet_id = request_data.get('subnet_id')
        description = request_data.get('description')
        add_subnet = request_data.get('add_subnet')
        add_description = request_data.get('add_description')
        add_master_id = request_data.get('add_master_id')
        room_group_name = request_data.get('room_group_name')
        auto_scan_subnet = request_data.get('auto_scan_subnet')
        if update:
            # 需要判断该地址原来状态是否自定义空闲的,自定义空闲的需要进行修改
            try:
                update_list = update
                for update_info in update_list:
                    ip_instance = IpAddress.objects.filter(ip_address=update_info['ipaddr']).first()
                    print(ip_instance)
                    if ip_instance and ip_instance.tag == 7:
                        # 执行修改
                        ip_instance.tag = update_info['tag']
                        ip_instance.description = update_info['description']
                        ip_instance.subnet_id = update_info['subnet_id']
                        ip_instance.save()
                    else:
                        IpAddress.objects.update_or_create(ip_address=update_info['ipaddr'],
                                                           subnet_id=update_info['subnet_id'],
                                                           defaults={
                                                               'tag': update_info['tag'],
                                                               'description': update_info['description'],
                                                           },
                                                           )
                        # tag = update_info['tag'],
                        # description = update_info['description'],
                res = {'message': '地址分配成功', 'code': 200, 'update_ip_list': [j['ipaddr'] for j in update_list]}
            except Exception as e:
                res = {'message': str(e), 'code': 400, }
            return JsonResponse(res, safe=True)
        if range_update:
            try:
                range_data = range_update
                print(range_data)
                start_ip = range_data['start_ip']
                end_ip = range_data['end_ip']
                description = range_data['description']
                subnet_id = range_data['subnet_id']
                update_ip_list = []
                for host_ip in iter_iprange(start_ip, end_ip):
                    # print(host_ip)

                    IpAddress.objects.update_or_create(
                        ip_address=str(host_ip),  # 查找关键字段
                        subnet_id=subnet_id,  # 查找关键字段
                        defaults={  # 更新字段
                            'tag': range_data['tag'],
                            'description': description
                        }
                    )
                    update_ip_list.append(str(host_ip))

                res = {'message': '地址批量分配成功', 'code': 200, 'update_ip_list': update_ip_list}
            except Exception as e:
                res = {'message': str(e), 'code': 400, }
            return JsonResponse(res, safe=True)
        if delete:
            try:
                delete_ip_list = delete
                print(delete_ip_list)
                for delete_info in delete_ip_list:
                    IpAddress.objects.filter(ip_address=delete_info['ipaddr']).delete()
                res = {'message': '地址回收成功', 'code': 200, 'delete_ip_list': [j['ipaddr'] for j in delete_ip_list]}
            except Exception as e:
                res = {'message': str(e), 'code': 400, }
            return JsonResponse(res, safe=True)

        if description:
            try:
                Subnet.objects.filter(id=subnet_id).update(description=description)
                res = {'message': '网段描述更新成功', 'code': 200}
            except Exception as e:
                res = {'message': str(e), 'code': 400, }
            return JsonResponse(res, safe=True)

        if add_subnet:
            try:
                print(add_master_id, type(add_master_id))
                master_subnet_id = Subnet.objects.filter(id=int(add_master_id)).first()
                add_kwargs = {
                    "name": add_subnet,
                    "mask": add_subnet.split("/")[1],
                    "subnet": add_subnet,
                    "description": add_description,
                    "master_subnet": master_subnet_id
                }
                subnet_list = [str(i.subnet) for i in Subnet.objects.all()]
                if add_master_id == "0":
                    add_kwargs.pop('master_subnet')
                    if add_subnet in subnet_list:
                        res = {'message': '新增网段失败,当前新增网段已经存在', 'code': 400, }
                    else:
                        Subnet.objects.update_or_create(**add_kwargs)
                        res = {'message': '新增网段成功', 'code': 200, }
                    return JsonResponse(res, safe=True)
                else:
                    master_subnet = Subnet.objects.get(id=add_master_id)
                    if str(master_subnet.subnet) == str(add_subnet):
                        res = {'message': '新增网段失败,请校验参数,不能新建跟父节点相同的子网段', 'code': 400, }
                        return JsonResponse(res, safe=True)
                    else:
                        # 校验IPV6
                        if ":" in str(master_subnet.subnet):

                            v6_master_subnet_detail = ipaddr.IPv6Network(str(master_subnet.subnet))
                            v6_add_subnet_detail = ipaddr.IPv6Network(str(str(add_subnet)))
                            if v6_add_subnet_detail in v6_master_subnet_detail:
                                if add_subnet in subnet_list:
                                    res = {'message': '新增网段失败,当前新增网段已经存在', 'code': 400, }
                                else:
                                    Subnet.objects.update_or_create(**add_kwargs)
                                    res = {'message': '新增网段成功', 'code': 200, }
                                return JsonResponse(res, safe=True)
                        # 校验IPV4
                        v4_master_subnet_detail = ipaddr.IPv4Network(str(master_subnet.subnet))
                        v4_add_subnet_detail = ipaddr.IPv4Network(str(str(add_subnet)))
                        if v4_add_subnet_detail in v4_master_subnet_detail:
                            if add_subnet in subnet_list:
                                res = {'message': '新增网段失败,当前新增网段已经存在', 'code': 400, }
                            else:
                                Subnet.objects.update_or_create(**add_kwargs)
                                res = {'message': '新增网段成功', 'code': 200, }

                        else:
                            res = {'message': '新增网段失败,请校验网段归属', 'code': 400, }
                        return JsonResponse(res, safe=True)
                # print(add_kwargs)
                # 校验是否有归属关系

                # print(str(master_subnet.subnet))
                # print(str(add_subnet))
                # print(str(add_subnet) == str(add_subnet))
                # 判断是否和父节点一致
            except Exception as e:
                res = {'message': e, 'code': 400, }
                return JsonResponse(res, safe=True)

        # if auto_scan_subnet:
        #     try:
        #         subnet_list = [str(i.subnet) for i in Subnet.objects.all()]
        #         if auto_scan_subnet in subnet_list:
        #             res = {'message': '当前网段已经存在,不执行扫描', 'code': 400, }
        #         else:
        #             # 需要先查询有没有父级网段-有父级网段则关联父级网段进行网段和地址新增、否则则进行网段新增和归属当前网段的地址新增
        #             """
        #             多线程确实可以实现异步操作，但这种异步性在执行CPU密集型任务时受到全局解释器锁（GIL）的限制。
        #             GIL是一个互斥锁，用于防止多个线程同时执行Python字节码。
        #             这意味着即使在多核处理器上，一个Python进程中的多个线程在任何时刻也只有一个可以执行Python代码。
        #             因此，对于CPU密集型任务，GIL实际上阻止了线程之间的并行执行，从而限制了多线程提高程序运行效率的能力。
        #             然而，对于I/O密集型任务，如文件读写、网络操作等，GIL的影响就相对较小。
        #             这是因为在执行这些操作时，线程可以释放GIL，从而允许其他线程运行。这就是为什么在I/O密集型场景下，使用多线程仍然可以提高程序的性能。
        #             auto_scan_task任务的描述，它主要是发送和接收网络数据包，这些操作主要是等待网络I/O的完成，而不是进行大量的计算。
        #             因此，我们可以合理推断auto_scan_task是一个I/O密集型任务。
        #             在执行过程中，大部分时间可能会花在等待网络I/O操作上，如等待ping请求的回应，而不是在执行计算密集的操作
        #             """
        #             t = threading.Thread(target=auto_scan_task, args=(auto_scan_subnet,))
        #             # 启动线程
        #             t.start()
        #             ip_count = get_subnet_address_count(auto_scan_subnet)
        #             # auto_scan_task(auto_scan_subnet)
        #             res = {'message': '网段扫描成功,新增网段{}成功添加{}个地址'.format('', ip_count - 2), 'code': 200, }
        #     except Exception as e:
        #         res = {'message': str(e), 'code': 400, }
        #     return JsonResponse(res, safe=True)


# 地址更新异步接口
# class IpUpdateAsyncTask(APIView):
#     def post(self, request):
#         try:
#             update_tasks = [ip_am_update_main()]
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             loop.run_until_complete(asyncio.wait(update_tasks))
#             loop.close()
#             res = {'message': "地址更新任务下发成功", 'code': 200, }
#         except Exception as e:
#             res = {'message': e, 'code': 400, }
#         return JsonResponse(res, safe=True)


# 地址回收异步接口
# class IpRecycleAsyncTask(APIView):
#     def post(self, request):
#         try:
#             recycle_tasks = [recycle_ip_main()]
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             loop.run_until_complete(asyncio.wait(recycle_tasks))
#             loop.close()
#             res = {'message': "地址回收任务下发成功", 'code': 200, }
#         except Exception as e:
#             res = {'message': e, 'code': 400, }
#
#         return JsonResponse(res, safe=True)


# phpipam子网段同步任务异步接口
# class PhpIpSubnetAsyncTask(APIView):
#     async def async_main(self):
#         await asyncio.gather(sync_ipam_subnet_main())
#
#     def post(self, request):
#         try:
#             # result = await asyncio.run(sync_ipam_subnet_main())
#             # print(result)
#             # subnet_async_tasks = [sync_ipam_subnet_main()]
#             # loop = asyncio.new_event_loop()  # 创建循环
#             # asyncio.set_event_loop(loop)  # 设置事件循环
#             # loop.run_until_complete(sync_ipam_subnet_main())
#             # loop.close()
#             asyncio.run(self.async_main())
#             res = {'message': "phpipam子网段同步任务下发成功", 'code': 200, }
#         except Exception as e:
#             res = {'message': e, 'code': 400, }
#         print(res)
#         return JsonResponse(res, safe=True)
#

# phpipam地址信息同步任务异步接口
# class PhpIpAsyncTask(APIView):
#     def post(self, request):
#         try:
#             ip_address_async_tasks = [sync_ipam_ipaddress_main()]
#             loop = asyncio.new_event_loop()
#             asyncio.set_event_loop(loop)
#             loop.run_until_complete(asyncio.wait(ip_address_async_tasks))
#             loop.close()
#             res = {'message': "phpipam地址信息同步任务下发成功", 'code': 200, }
#         except Exception as e:
#             res = {'message': e, 'code': 400, }
#
#         return JsonResponse(res, safe=True)


# def check_api_key(func):
#     auth_check = ApiKeyAuthentication()
#
#     def wrap(view, request):
#         if request.headers.get('Authorization', ''):
#             if 'api-key' in request.headers['Authorization']:
#                 auth_check.authenticate(request)
#                 return func(view, request)
#             else:
#                 raise AuthenticationFailed('Invalid api-key header. No credentials provided.')
#         raise AuthenticationFailed('Invalid api-key header. No credentials provided.')
#
#     return wrap


class IpamOpenAPI(APIView):
    # @check_api_key
    def post(self, request):
        post_params = request.data
        # 更新网段下的网络类型
        update = post_params.get('update')
        subnet = post_params.get('subnet')
        network_type = post_params.get('network_type')
        # 查询网段或者地址的网络类型
        search = post_params.get('search')
        search_key = post_params.get('search_key')
        # 更新地址都寻觅信息
        update_xunmi = post_params.get('update_xunmi')
        ip_addr = post_params.get('ip_addr')
        xunmi_info = post_params.get('xunmi_info')
        if update:
            try:
                subnet_instance = Subnet.objects.filter(name=subnet).first()
                if subnet_instance:
                    subnet_instance.network_type = network_type
                    subnet_instance.save()
                    res = {'message': "更新网段网络类型成功", 'code': 200,
                           'results': f'{subnet}-更新网络类型成功-{network_type}'}
                else:
                    res = {'message': "更新网段网络类型失败", 'code': 400,
                           'results': f'暂无该网段{subnet}'}
            except Exception as e:
                res = {'message': str(e), 'code': 400, 'results': ''}
            return JsonResponse(res, safe=True)
        if search:
            try:
                if '/32' in search_key:
                    ip_addr = search_key.split('/')[0]
                    # 查询当前地址归属网段的网络类型字段
                    IpInstance = IpAddress.objects.filter(ip_address=ip_addr).first()
                    search_key = str(IpInstance.subnet.name)
                    subnet_data = Subnet.objects.filter(name=search_key).all()
                else:
                    # 查询网段的网络类型字段
                    subnet_data = Subnet.objects.filter(name=search_key).all()

                tmp_serializer = SubnetSerializer(subnet_data, many=True)
                res = {'message': "查询网络类型成功", 'code': 200, 'results': tmp_serializer.data}
            except Exception as e:
                res = {'message': str(e), 'code': 400, 'results': ''}
            return JsonResponse(res, safe=True)

        if update_xunmi:
            try:
                ip_instance = IpAddress.objects.filter(ip_address=ip_addr).first()
                if ip_instance:
                    ip_instance.xunmi_info = xunmi_info
                    ip_instance.save()
                    res = {'message': "更新地址的寻觅信息成功", 'code': 200,
                           'results': f'{ip_addr}-更新地址的寻觅信息成功-{xunmi_info}'}
                else:
                    res = {'message': "更新地址的寻觅信息失败", 'code': 400,
                           'results': f'暂无该地址-{ip_addr}-更新地址的寻觅信息失败'}
            except Exception as e:
                res = {'message': str(e), 'code': 400, 'results': ''}
            return JsonResponse(res, safe=True)

    def get(self, request):
        get_params = request.GET.dict()
        api_key_token = ApiKeyToken()
        platform = get_params.get('platform', 'netops')
        # 获取传参平台
        # api_key_token.platform = platform
        # 先查询平台是否有存活的key且未过期
        platform_key_queryset = ApiKeyToken.objects.filter(platform=platform)
        print('platform_key_queryset.expireTime', platform_key_queryset)
        platform_key_instance = platform_key_queryset.first()
        if platform_key_queryset:
            if platform_key_instance.expireTime > datetime.now():
                # 更新记录时间
                print('未过期则更新key使用get时间')
                message = 'platform存在且未过期则更新key的使用get时间'
                platform_key_queryset.update(key=platform_key_instance.key, expireTime=platform_key_instance.expireTime,
                                             lastGetTime=datetime.now())
                res = {'api-key': platform_key_instance.key,
                       'platform': platform,
                       'code': 200,
                       'results': 'success',
                       'message': message,
                       'expireTime': platform_key_instance.expireTime}
                return JsonResponse(res, safe=True)
            else:
                print('apikey过期更新key', datetime.now() + timedelta(hours=1))
                message = 'platform存在但apikey过期更新key'
                new_key = api_key_token.generate_key()
                new_expire_time = datetime.now() + timedelta(hours=1)
                platform_key_queryset.update(key=new_key, expireTime=new_expire_time)
                res = {'api-key': new_key,
                       'platform': platform,
                       'code': 200,
                       'results': 'success',
                       'message': message,
                       'expireTime': new_expire_time}
                return JsonResponse(res, safe=True)
        else:
            # 新增
            print('platform不存在新增apikey', platform, datetime.now() + timedelta(hours=1))
            message = 'platform不存在新增apikey'
            api_key_token.platform = platform
            api_key_token.key = api_key_token.generate_key()
            api_key_token.lastGetTime = datetime.now()
            api_key_token.expireTime = datetime.now() + timedelta(hours=1)
            api_key_token.save()
            # 返回响应
            res = {'api-key': api_key_token.key,
                   'platform': platform,
                   'code': 200,
                   'results': 'success',
                   'message': message,
                   'expireTime': api_key_token.expireTime}
            return JsonResponse(res, safe=True)
