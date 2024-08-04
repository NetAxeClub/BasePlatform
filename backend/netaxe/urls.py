"""netaxe URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.views.static import serve

from netaxe import views, settings
# from drf_yasg import openapi
from django.contrib import admin
from django.urls import include, path, re_path
# from drf_yasg.views import get_schema_view
from rest_framework import permissions
from apps.system.views.login import (
    LoginView,
    LogoutView,
    LoginViewSet,
)
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenObtainPairView
)

# schema_view = get_schema_view(
#     openapi.Info(
#         title="Snippets API",
#         default_version="v1",
#     ),
#     public=True,
#     permission_classes=[permissions.AllowAny, ],
# )

urlpatterns = [
    path('admin/', admin.site.urls, name="admin"),
    # path('admin/login/', views.extend_admin_login, name="login"),
    re_path(r'^base_platform/media/(?P<path>.*)', serve, {"document_root": settings.MEDIA_ROOT}),
    # re_path(r'^captcha/', include('captcha.urls')),
    # path("swagger/",schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui",),
    re_path('^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    # 登录
    path("base_platform/login/", LoginView.as_view(), name="login"),
    path("base_platform/logout/", LogoutView.as_view(), name="logout"),
    path("base_platform/status/", LoginViewSet.as_view(), name="status"),
    path('base_platform/token/', TokenObtainPairView.as_view(), name='get_jwt_token'),
    path("base_platform/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # 自定义权限
    path("base_platform/users/", include("apps.users.urls"), name="users"),
    # path("base_platform/system/", include("apps.system.urls")),

    path(r'base_platform/asset/', include('apps.asset.urls'), name="asset"),
    path(r'base_platform/backend/', include('apps.route_backend.urls'), name="backend"),
    path(r'base_platform/automation/', include('apps.automation.urls'), name="automation"),
    path(r'base_platform/config_center/', include('apps.config_center.urls'), name="config_center"),
    path(r'base_platform/int_utilization/', include('apps.int_utilization.urls'), name="int_utilization"),
    path(r'base_platform/topology/', include('apps.topology.urls'), name="topology"),
    path(r'base_platform/system/', include('apps.system.urls'), name="system"),
    path(r'base_platform/dcs_manage/', include('apps.dcs_control.urls'), name="dcs_control"),
]
