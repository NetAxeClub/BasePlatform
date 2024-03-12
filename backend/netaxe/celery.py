# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      celery
   Description:
   Author:          Lijiamin
   date：           2022/7/29 14:25
-------------------------------------------------
   Change Activity:
                    2022/7/29 14:25
-------------------------------------------------
"""
from __future__ import absolute_import, unicode_literals
import os
from celery_once import QueueOnce
from django.apps import apps
# set the default Django settings module for the 'celery' program.
from django.utils import timezone
from kombu import Queue, Exchange
from celery import Celery, platforms
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netaxe.settings')

app = Celery('netaxe')

app.conf.ONCE = {
  'backend': 'celery_once.backends.Redis',
  'settings': {
    'url': settings.CELERY_ONCE_URL,
    'default_timeout': 60 * 60
  }
}

app.now = timezone.now
app.config_from_object('django.conf:settings', namespace='CELERY')

default_exchange = Exchange('default', type='direct')
config_exchange = Exchange('config', type='direct')
ipam_exchange = Exchange('ipam', type='direct')
xunmi_exchange = Exchange('xunmi', type='direct')
dev_exchange = Exchange('dev', type='direct')

app.conf.task_time_limit = 86400
app.conf.worker_prefetch_multiplier = 10
app.conf.worker_max_tasks_per_child = 100
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'
app.conf.task_default_exchange_type = 'direct'
app.conf.task_queues = (
    Queue('default', default_exchange, routing_key='default'),
    Queue('config', config_exchange, routing_key='config'),
    Queue('ipam', ipam_exchange, routing_key='ipam'),
    Queue('xunmi', xunmi_exchange, routing_key='ipam'),
    Queue('dev', dev_exchange, routing_key='dev'),
)
platforms.C_FORCE_ROOT = True
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])


class AxeTask(QueueOnce):

    # def run(self, *args, **kwargs):
    #     pass

    max_retries = 3
    # autoretry_for = (Exception, KeyError, RuntimeError)
    retry_kwargs = {'max_retries': 1}
    retry_backoff = False

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        print(str(einfo))
        return super(AxeTask, self).on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        # print('task retry, reason: {0}'.format(exc))
        print(str(einfo))
        return super(AxeTask, self).on_failure(exc, task_id, args, kwargs, einfo)