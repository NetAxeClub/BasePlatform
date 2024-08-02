# -*- coding: utf-8 -*-
"""
-------------------------------------------------
   File Name：      urls
   Description:
   Author:          Lijiamin
   date：           2024/8/2 15:41
-------------------------------------------------
   Change Activity:
                    2024/8/2 15:41
-------------------------------------------------
"""
from django.urls import path, include
from rest_framework_extensions.routers import (
    ExtendedDefaultRouter as DefaultRouter
)

from apps.dcs_control import views

app_name = 'dcs_control'

urlpatterns = [
    path('deny_key/', views.DenyByAddrObj.as_view(), name="deny_key"),  # 一键封堵

]