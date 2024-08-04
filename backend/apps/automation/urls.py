from django.urls import path, include
from rest_framework_extensions.routers import (
    ExtendedDefaultRouter as DefaultRouter
)
from .views import (
    CollectionPlanViewSet, CollectionRuleViewSet,
    CollectionMatchRuleViewSet, VueCollectionRule, AutomationInventoryViewSet, AutoVarsViewSet,
    AutoFlowViewSet, AutomationChart, XunMiView, SecMainView)
app_name = 'automation'

router = DefaultRouter()
router.register(r'api/collection_plan', CollectionPlanViewSet, basename='CollectionPlanViewSet')
router.register(r'api/collection_rule', CollectionRuleViewSet, basename='CollectionRuleViewSet')
router.register(r'api/auto_work_flow', AutoFlowViewSet, basename='CollectionRuleViewSet')
router.register(r'api/auto_inventory', AutomationInventoryViewSet, basename='AutomationInventoryViewSet')
router.register(r'api/auto_host_vars', AutoVarsViewSet, basename='AutoVarsViewSet')
router.register(r'api/collection_match_rule', CollectionMatchRuleViewSet, basename='CollectionMatchRuleViewSet')

urlpatterns = [
    path(r'', include(router.urls)),
    path('collection_rule/', VueCollectionRule.as_view(), name="collection_rule"),
    path('automation_chart/', AutomationChart.as_view(), name="automation_chart"),
    path('address_location/', XunMiView.as_view(), name="address_location"),
    path('sec_main/', SecMainView.as_view(), name="sec_main")
]
