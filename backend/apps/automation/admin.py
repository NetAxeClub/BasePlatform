from django.contrib import admin
from .models import CollectionPlan, CollectionRule, CollectionMatchRule, AutoFlow

# Register your models here.
admin.site.register(CollectionPlan)
admin.site.register(CollectionRule)
admin.site.register(AutoFlow)
admin.site.register(CollectionMatchRule)