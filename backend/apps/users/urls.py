from django.urls import path, include
from rest_framework.routers import SimpleRouter

from apps.users.views.user import UserViewSet


router = SimpleRouter()
router.register(r'user', UserViewSet)
# router.register(r'bgbu', BgBuViewSet)

urlpatterns = [
    path(r'', include(router.urls)),
]