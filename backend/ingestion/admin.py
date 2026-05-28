from django.contrib import admin
from .models import IngestionJob, EmissionRecord, AuditLog


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'source_type', 'original_filename', 'status', 'row_count', 'created_at']
    list_filter = ['source_type', 'status']


@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'scope', 'category', 'activity_type', 'quantity', 'unit', 'co2e_kg', 'status', 'is_locked']
    list_filter = ['scope', 'category', 'status', 'is_locked', 'ingestion_job__source_type']
    search_fields = ['activity_type', 'facility', 'source_row_id']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'record', 'action', 'actor', 'timestamp']
    list_filter = ['action']
    readonly_fields = ['before_state', 'after_state', 'timestamp']
