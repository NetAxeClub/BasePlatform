#!/bin/bash
#license:MIT
#Another:jmli12
#date:2023.1.4
# cd /home/netaxe && git pull
# pip3 install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
# pip3 install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
python3 manage.py makemigrations users
python3 manage.py migrate users
python3 manage.py makemigrations automation
python3 manage.py migrate automation
python3 manage.py makemigrations int_utilization
python3 manage.py migrate int_utilization
python3 manage.py makemigrations network_analysis
python3 manage.py migrate network_analysis
python3 manage.py makemigrations topology
python3 manage.py migrate topology
# open_ipam app 不存在，已注释
# python3 manage.py makemigrations open_ipam
# python3 manage.py migrate open_ipam
python3 manage.py makemigrations
python3 manage.py migrate
python3 manage.py init_asset # 资产初始化
python3 manage.py init_collect # 采集方案初始化
#python3 manage.py init_system_menu # 系统菜单初始化

echo "init success!"
echo "starting web server!"
sh start.sh web
