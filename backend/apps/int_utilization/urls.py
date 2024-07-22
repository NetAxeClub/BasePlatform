from django.urls import path, include
from rest_framework_extensions.routers import (
    ExtendedDefaultRouter as DefaultRouter
)

# from apps.int_utilization import views
from .views import InterfaceUsedNewViewSet, InterfaceView


router = DefaultRouter()

router.register(r'interfaceused', InterfaceUsedNewViewSet)

urlpatterns = [
    path(r'', include(router.urls)),
    path('interface/', InterfaceView.as_view(), name="interface")
]
