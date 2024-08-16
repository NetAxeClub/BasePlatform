from django.contrib import admin
from .models import CollectionPlan, CollectionRule, CollectionMatchRule, AutoFlow

# Register your models here.
admin.site.register(CollectionPlan)
admin.site.register(CollectionRule)
admin.site.register(CollectionMatchRule)


@admin.register(AutoFlow)
class FSMModelAdmin(admin.ModelAdmin):
    list_display = ['task_id', 'device', 'commit_user', 'commit_time', 'task', 'kwargs', 'state', 'task_result']
    search_fields = ['task_id', 'device', 'commit_user', 'commit_time', 'task', 'kwargs', 'state', 'task_result']
