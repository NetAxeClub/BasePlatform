#!/bin/bash

web(){
    mkdir -p /var/log/supervisor
    echo 'uwsgi done'
    supervisord -n -c /app/supervisord_prd.conf
}

default(){
    local worker_count=${2:-20}
    mkdir -p /app/logs/celery_logs
    celery -A netaxe worker -Q default -c $worker_count -l info -n default
}

config(){
    local worker_count=${2:-40}
    mkdir -p /app/logs/celery_logs
    celery -A netaxe worker -Q config -c $worker_count -l info -n config
}

xunmi(){
    local worker_count=${2:-20}
    mkdir -p /app/logs/celery_logs
    celery -A netaxe worker -Q xunmi -c $worker_count -l info -n xunmi
}

case "$1" in
web)
    web
    ;;
default)
    default "$@"
    ;;
config)
    config "$@"
    ;;
xunmi)
    xunmi "$@"
    ;;
*)
    echo "Usage: $0 {web|default|config|xunmi} [worker_count]"
    echo "  web: 启动 web 服务"
    echo "  default: 启动 default worker (默认 20 个 worker)"
    echo "  config: 启动 config worker (默认 40 个 worker)"
    echo "  xunmi: 启动 xunmi worker (默认 20 个 worker)"
    echo "  示例: $0 default 30  # 启动 default worker，使用 30 个 worker"
    exit 1
    ;;
esac
echo "start running!"