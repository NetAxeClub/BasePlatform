from django.urls import path, include
from rest_framework_extensions.routers import (
    ExtendedDefaultRouter as DefaultRouter
)
from .views import (
    CollectionPlanViewSet, CollectionRuleViewSet,
    CollectionMatchRuleViewSet, VueCollectionRule, AutoFlowViewSet, AutomationChart, XunMiView)
app_name = 'automation'

router = DefaultRouter()
router.register(r'api/collection_plan', CollectionPlanViewSet, basename='CollectionPlanViewSet')
router.register(r'api/collection_rule', CollectionRuleViewSet, basename='CollectionRuleViewSet')
router.register(r'api/auto_work_flow', AutoFlowViewSet, basename='CollectionRuleViewSet')
router.register(r'api/collection_match_rule', CollectionMatchRuleViewSet, basename='CollectionMatchRuleViewSet')

urlpatterns = [
    path(r'', include(router.urls)),
    path('collection_rule/', VueCollectionRule.as_view(), name="collection_rule"),
    path('automation_chart/', AutomationChart.as_view(), name="automation_chart"),
    path('address_location/', XunMiView.as_view(), name="address_location")
]
