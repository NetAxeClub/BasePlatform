from django.contrib import admin
from .models import CollectionPlan, CollectionRule, CollectionMatchRule

# Register your models here.
admin.site.register(CollectionPlan)
admin.site.register(CollectionRule)
admin.site.register(CollectionMatchRule)