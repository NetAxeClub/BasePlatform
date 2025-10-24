from django.contrib import admin
from django.utils.html import format_html
from apps.device_api.models import DeviceCollectionPlans, DeviceSubCollectionPlan, NetconfXMLTemplate


@admin.register(DeviceCollectionPlans)
class DeviceCollectionPlansAdmin(admin.ModelAdmin):
    """采集汇总方案管理"""
    list_display = [
        'name', 'vendor', 'device_type', 'is_active', 'collect_plans_count', 'created_at'
    ]
    list_filter = [
        'vendor', 'device_type', 'is_active', 'created_at'
    ]
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['vendor', 'device_type', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'vendor', 'device_type', 'description', 'is_active')
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).prefetch_related('collect_plans')
    
    def collect_plans_count(self, obj):
        """显示采集方案数量"""
        count = obj.collect_plans.count()
        return format_html('<span style="color: {};">{}</span>', 
                         'green' if count > 0 else 'red', count)
    collect_plans_count.short_description = '采集方案数量'


@admin.register(DeviceSubCollectionPlan)
class DeviceSubCollectionPlanAdmin(admin.ModelAdmin):
    """设备采集方案管理"""
    list_display = [
        'name', 'summary_plan', 'vendor_display', 'device_type_display', 'netmiko_enabled', 'netconf_enabled', 
        'netmiko_method', 'textfsm_enabled', 
        'netmiko_processor_enabled', 'netconf_processor_enabled', 'xml_templates_count', 'created_at'
    ]
    list_filter = [
        'summary_plan__vendor', 'summary_plan__device_type', 'netmiko_enabled', 'netconf_enabled',
        'textfsm_enabled', 'netmiko_processor_enabled', 'netconf_processor_enabled', 'created_at'
    ]
    search_fields = ['name', 'description', 'netmiko_method', 'summary_plan__name']
    readonly_fields = ['created_at', 'updated_at', 'vendor_display', 'device_type_display']
    ordering = ['summary_plan__vendor', 'summary_plan__device_type', 'name']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('name', 'summary_plan', 'description')
        }),
        ('采集方式配置', {
            'fields': ('netmiko_enabled', 'netconf_enabled')
        }),
        ('Netmiko配置', {
            'fields': ('netmiko_method', 'netmiko_path', 'netmiko_field_mappings', 'netmiko_processor_enabled', 'netmiko_processor'),
            'classes': ('collapse',)
        }),
        ('NETCONF配置', {
            'fields': ('netconf_path', 'netconf_field_mappings', 'netconf_processor_enabled', 'netconf_processor'),
            'classes': ('collapse',)
        }),
        ('TextFSM配置', {
            'fields': ('textfsm_enabled', 'textfsm_template'),
            'classes': ('collapse',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).select_related('summary_plan').prefetch_related('xml_templates')
    
    def vendor_display(self, obj):
        """显示厂商信息"""
        if obj.summary_plan:
            return obj.summary_plan.get_vendor_display()
        return '-'
    vendor_display.short_description = '厂商'
    
    def device_type_display(self, obj):
        """显示设备类型"""
        if obj.summary_plan:
            return obj.summary_plan.device_type
        return '-'
    device_type_display.short_description = '设备类型'
    
    def xml_templates_count(self, obj):
        """显示XML模板数量"""
        count = obj.xml_templates.count()
        return format_html('<span style="color: {};">{}</span>', 
                         'green' if count > 0 else 'red', count)
    xml_templates_count.short_description = 'XML模板数量'


@admin.register(NetconfXMLTemplate)
class NetconfXMLTemplateAdmin(admin.ModelAdmin):
    """NETCONF XML模板管理"""
    list_display = [
        'collect_method', 'collection_plan', 'created_at', 'updated_at'
    ]
    list_filter = [
        'collection_plan__summary_plan__vendor', 'collection_plan__summary_plan__device_type', 
        'collect_method', 'created_at'
    ]
    search_fields = ['collect_method', 'description', 'collection_plan__name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['collection_plan', 'collect_method']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('collect_method', 'collection_plan', 'description')
        }),
        ('模板内容', {
            'fields': ('xml_template',)
        }),
        ('时间信息', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """优化查询"""
        return super().get_queryset(request).select_related('collection_plan', 'collection_plan__summary_plan')
    
    def collection_plan_info(self, obj):
        """显示采集方案信息"""
        if obj.collection_plan and obj.collection_plan.summary_plan:
            return format_html(
                '<span style="color: blue;">{}</span><br>'
                '<small style="color: gray;">{}-{}</small>',
                obj.collection_plan.name,
                obj.collection_plan.summary_plan.get_vendor_display(),
                obj.collection_plan.summary_plan.device_type
            )
        return '-'
    collection_plan_info.short_description = '采集方案信息'


