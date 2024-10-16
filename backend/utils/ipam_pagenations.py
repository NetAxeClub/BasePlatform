from collections import OrderedDict

from rest_framework import pagination
from rest_framework.response import Response
from rest_framework.utils.urls import replace_query_param, remove_query_param

from apps.open_ipam.models import Subnet


class HostsListPagination(pagination.BasePagination):
    limit = 256
    start_query_param = 'start'

    def paginate_queryset(self, queryset, request, view=None):
        self.count = queryset.count()
        self.queryset = queryset
        self.request = request
        self.offset = self.get_offset(request)
        return list(queryset[self.offset: self.offset + self.limit])  # noqa

    def get_paginated_response(self, data):
        # start_time = time.time() * 1000
        empty = round(len([i for i in data if i['tag'] == 1]) * 100 / len(data), 2)
        dist_and_used = round(len([i for i in data if i['tag'] == 2]) * 100 / len(data), 2)
        reserved = round(len([i for i in data if i['tag'] == 3]) * 100 / len(data), 2)
        not_dist_used = round(len([i for i in data if i['tag'] == 4]) * 100 / len(data), 2)
        dist_not_used = round(len([i for i in data if i['tag'] == 6]) * 100 / len(data), 2)
        self_empty = round(len([i for i in data if i['tag'] == 7]) * 100 / len(data), 2)
        # end_time = time.time() * 1000
        # print("Request page %.2f ms" % (end_time - start_time))
        return Response(
            OrderedDict(
                [
                    ('next', self.get_next_link()),
                    ('previous', self.get_previous_link()),
                    ('results', data),
                    ('code', 200),
                    # ('ip_used', [i for i in data]),
                    ('data', {'ip_used': data,
                              'sub_net': Subnet.objects.filter(subnet=data[0]['subnet']).values("name", "description",
                                                                                                "id"),
                              'subnet_used_count': {
                                  'empty_count': len([i for i in data if i['tag'] == 1]),
                                  'dist_and_used_count': len([i for i in data if i['tag'] == 2]),
                                  'reserved_count': len([i for i in data if i['tag'] == 3]),
                                  'not_dist_used_count': len([i for i in data if i['tag'] == 4]),
                                  'dist_not_used_count': len([i for i in data if i['tag'] == 6]),
                                  'self_empty_count': len([i for i in data if i['tag'] == 7]),
                                  "total_count": len(data)
                              },
                              'subnet_used': {
                                  'freehosts': round(100 - dist_and_used - not_dist_used, 2),
                                  'freehosts_percent': round(100 - dist_and_used - not_dist_used, 2),
                                  'maxhosts': len(data),
                                  'used': round(dist_and_used + not_dist_used, 2),
                                  'Used_percent': round(dist_and_used + not_dist_used, 2),
                                  'empty_percent': empty,
                                  '自定义空闲_percent': self_empty,
                                  '已分配已使用_percent': dist_and_used,
                                  '保留_percent': reserved,
                                  '未分配已使用_percent': not_dist_used,
                                  '已分配未使用_percent': dist_not_used,
                              }}),
                ]
            )
        )

    def get_offset(self, request):
        try:
            return self.queryset.index_of(request.query_params[self.start_query_param])
        except (KeyError, ValueError):
            return 0

    def get_next_link(self):
        if self.offset + self.limit >= self.count:
            return None
        url = self.request.build_absolute_uri()
        offset = self.offset + self.limit
        return replace_query_param(
            url, self.start_query_param, self.queryset[offset].address
        )

    def get_previous_link(self):
        if self.offset <= 0:
            return None
        url = self.request.build_absolute_uri()
        if self.offset - self.limit <= 0:
            return remove_query_param(url, self.start_query_param)
        offset = self.offset - self.limit
        return replace_query_param(
            url, self.start_query_param, self.queryset[offset].address
        )
