from django.contrib.auth.decorators import login_required
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

app_name = 'topology'
router = DefaultRouter()


# router.register(r'index', TopologyViewSet)


urlpatterns = [
    path(r'', include(router.urls)),
    path('list/', TopologyList.as_view(), name='list'),
    path('create/', TopologyCreate.as_view(), name='create'),
    path('index/', TopologyShow.as_view(), name='show'),
    path('icon/', IconView.as_view(), name='icon'),
]
