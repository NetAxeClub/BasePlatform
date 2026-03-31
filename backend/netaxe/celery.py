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
import logging
from celery_once import QueueOnce
from django.apps import apps
# set the default Django settings module for the 'celery' program.
from django.utils import timezone
from kombu import Queue, Exchange
from celery import Celery, platforms, signals
from asgiref.sync import async_to_sync
from channels.layers import channel_layers, get_channel_layer
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netaxe.settings')
logger = logging.getLogger(__name__)

app = Celery('netaxe')
app.config_from_object(dict(result_extended=True))
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
    Queue('xunmi', xunmi_exchange, routing_key='xunmi'),
    Queue('dev', dev_exchange, routing_key='dev'),
)
platforms.C_FORCE_ROOT = True
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])


@signals.worker_process_init.connect
def _reset_channels_backend_in_child(**kwargs):
    """Celery prefork 子进程启动时重置 channels backend，避免复用父进程状态。"""
    try:
        channel_layers._reset_backends()  # noqa: SLF001 - channels 官方管理器提供的方法
    except Exception as exc:
        logger.warning("worker_process_init reset channels backend failed: %s", exc)


@signals.worker_process_shutdown.connect
def _close_channels_pools_in_child(**kwargs):
    """Celery 子进程退出前关闭 channels redis 连接池，减少 loop 关闭噪声。"""
    try:
        layer = get_channel_layer()
        if layer and hasattr(layer, "close_pools"):
            async_to_sync(layer.close_pools)()
    except RuntimeError:
        # 进程退出阶段 loop 可能已关闭，避免再次放大无效错误。
        logger.debug("worker_process_shutdown close channels pools skipped: event loop closed")
    except Exception as exc:
        logger.warning("worker_process_shutdown close channels pools failed: %s", exc)


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