from rest_framework import serializers
from core.models import Organization
from .models import IngestionJob, EmissionRecord, AuditLog


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug', 'created_at']


class IngestionJobSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'organization', 'source_type', 'source_type_display',
            'original_filename', 'status', 'status_display',
            'created_at', 'completed_at', 'row_count', 'error_count', 'error_log',
        ]


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    source_type = serializers.CharField(source='ingestion_job.source_type', read_only=True)
    reviewed_by_username = serializers.CharField(source='reviewed_by.username', read_only=True, default=None)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'organization', 'ingestion_job', 'source_type', 'source_row_id',
            'scope', 'scope_display', 'category', 'category_display', 'activity_type',
            'period_start', 'period_end',
            'quantity', 'unit', 'quantity_normalized', 'normalized_unit', 'co2e_kg',
            'facility', 'country',
            'status', 'status_display', 'review_notes',
            'reviewed_by_username', 'reviewed_at',
            'flags', 'is_locked',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_locked']


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ['id', 'record', 'action', 'actor_username', 'before_state', 'after_state', 'notes', 'timestamp']
