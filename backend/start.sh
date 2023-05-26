#!/bin/bash



web(){
    mkdir -p /app/logs/celery_logs
    mkdir -p /var/log/supervisor
    echo 'uwsgi done'
    supervisord -n -c /app/supervisord_prd.conf
}

case "$1" in
web)
web
;;
*)
echo "Usage: $1 {web}"
;;
esac
echo "start running!"