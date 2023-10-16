#!/bin/bash



web(){
    mkdir -p /var/log/supervisor
    echo 'uwsgi done'
    supervisord -n -c /app/supervisord_prd.conf
}
default(){
    mkdir -p /app/logs/celery_logs
    celery -A netaxe worker -Q default -c 20  -l info -n default
}
config(){
    mkdir -p /app/logs/celery_logs
    celery -A netaxe worker -Q config -c 40  -l info -n config
}
case "$1" in
web)
web
;;
default)
default
;;
config)
config
;;
*)
echo "Usage: $1 {web|default|config}"
;;
esac
echo "start running!"