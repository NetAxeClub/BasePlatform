from django.contrib import admin

from apps.dcs_control.models import BlockRecord, DnatRecord, FirewallPolicyAuditRecord


@admin.register(BlockRecord)
class BlockRecordAdmin(admin.ModelAdmin):
    list_display = ("inventory_id", "action", "operator", "status", "created_at")
    search_fields = ("operator", "inventory_id")
    list_filter = ("action", "status", "created_at")


@admin.register(DnatRecord)
class DnatRecordAdmin(admin.ModelAdmin):
    list_display = ("vendor", "device_ip", "rule_name", "public_ip", "private_ip", "status", "created_at")
    search_fields = ("rule_name", "public_ip", "private_ip", "device_ip")
    list_filter = ("vendor", "status", "created_at")


@admin.register(FirewallPolicyAuditRecord)
class FirewallPolicyAuditRecordAdmin(admin.ModelAdmin):
    list_display = ("vendor", "device_ip", "audit_type", "status", "source", "created_at")
    search_fields = ("device_ip", "vendor", "task_id", "operator")
    list_filter = ("vendor", "audit_type", "status", "source", "created_at")
