from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from django.db.models import Count, Q, Sum
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import action

from core.models import Organization
from .models import IngestionJob, EmissionRecord, AuditLog
from .serializers import (
    IngestionJobSerializer,
    EmissionRecordSerializer,
    OrganizationSerializer,
)
from .parsers import sap, utility, travel


PARSERS = {
    IngestionJob.SOURCE_SAP: sap.parse,
    IngestionJob.SOURCE_UTILITY: utility.parse,
    IngestionJob.SOURCE_TRAVEL: travel.parse,
}


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class IngestionJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IngestionJob.objects.all()
    serializer_class = IngestionJobSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        org_id = self.request.query_params.get('organization')
        if org_id:
            qs = qs.filter(organization_id=org_id)
        return qs


class EmissionRecordViewSet(viewsets.ModelViewSet):
    queryset = EmissionRecord.objects.select_related('ingestion_job', 'reviewed_by').all()
    serializer_class = EmissionRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        if org := params.get('organization'):
            qs = qs.filter(organization_id=org)
        if scope := params.get('scope'):
            qs = qs.filter(scope=scope)
        if src := params.get('source_type'):
            qs = qs.filter(ingestion_job__source_type=src)
        if record_status := params.get('status'):
            qs = qs.filter(status=record_status)
        if flagged := params.get('flagged'):
            if flagged == 'true':
                qs = qs.exclude(flags=[])

        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        return self._set_status(request, EmissionRecord.STATUS_APPROVED, AuditLog.ACTION_APPROVED)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        return self._set_status(request, EmissionRecord.STATUS_REJECTED, AuditLog.ACTION_REJECTED)

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        return self._set_status(request, EmissionRecord.STATUS_FLAGGED, AuditLog.ACTION_FLAGGED)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        record = self.get_object()
        if record.status != EmissionRecord.STATUS_APPROVED:
            return Response({'error': 'Only approved records can be locked.'}, status=400)
        before = {'status': record.status, 'is_locked': record.is_locked}
        record.is_locked = True
        record.save(update_fields=['is_locked', 'updated_at'])
        AuditLog.objects.create(
            organization=record.organization,
            record=record,
            action=AuditLog.ACTION_LOCKED,
            actor=request.user if request.user.is_authenticated else None,
            before_state=before,
            after_state={'status': record.status, 'is_locked': True},
        )
        return Response(EmissionRecordSerializer(record).data)

    def _set_status(self, request, new_status, action):
        record = self.get_object()
        if record.is_locked:
            return Response({'error': 'Record is locked for audit.'}, status=400)
        before = {'status': record.status}
        notes = request.data.get('notes', '')
        record.status = new_status
        record.reviewed_by = request.user if request.user.is_authenticated else None
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        record.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])
        AuditLog.objects.create(
            organization=record.organization,
            record=record,
            action=action,
            actor=record.reviewed_by,
            before_state=before,
            after_state={'status': new_status},
            notes=notes,
        )
        return Response(EmissionRecordSerializer(record).data)


class IngestFileView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        org_id = request.data.get('organization')
        source_type = request.data.get('source_type')
        file_obj = request.FILES.get('file')

        if not all([org_id, source_type, file_obj]):
            return Response({'error': 'organization, source_type, and file are required.'}, status=400)

        if source_type not in PARSERS:
            return Response({'error': f'Unknown source_type "{source_type}".'}, status=400)

        try:
            org = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found.'}, status=404)

        job = IngestionJob.objects.create(
            organization=org,
            source_type=source_type,
            uploaded_file=file_obj,
            original_filename=file_obj.name,
            status=IngestionJob.STATUS_PROCESSING,
            uploaded_by=request.user if request.user.is_authenticated else None,
        )

        try:
            content = file_obj.read()
            parse_fn = PARSERS[source_type]
            records_data, errors = parse_fn(content)

            created = []
            for rd in records_data:
                rec = EmissionRecord.objects.create(
                    organization=org,
                    ingestion_job=job,
                    **rd,
                )
                created.append(rec)

            job.status = IngestionJob.STATUS_COMPLETED
            job.completed_at = timezone.now()
            job.row_count = len(created)
            job.error_count = len(errors)
            job.error_log = errors
            job.save()

        except Exception as exc:
            job.status = IngestionJob.STATUS_FAILED
            job.error_log = [str(exc)]
            job.save(update_fields=['status', 'error_log'])
            return Response({'error': str(exc)}, status=500)

        return Response(IngestionJobSerializer(job).data, status=201)


class DashboardSummaryView(APIView):
    def get(self, request):
        org_id = request.query_params.get('organization')
        qs = EmissionRecord.objects.all()
        if org_id:
            qs = qs.filter(organization_id=org_id)

        by_scope = list(
            qs.values('scope').annotate(count=Count('id'), total_co2e=Sum('co2e_kg'))
        )
        by_status = list(
            qs.values('status').annotate(count=Count('id'))
        )
        by_source = list(
            qs.values('ingestion_job__source_type').annotate(count=Count('id'))
        )
        flagged_count = qs.exclude(flags=[]).count()
        total_co2e = qs.aggregate(total=Sum('co2e_kg'))['total'] or 0

        return Response({
            'total_records': qs.count(),
            'total_co2e_kg': float(total_co2e),
            'flagged_count': flagged_count,
            'by_scope': by_scope,
            'by_status': by_status,
            'by_source': by_source,
        })


class LoginView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return Response({'username': user.username, 'id': user.id})
        return Response({'error': 'Invalid credentials'}, status=401)


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'status': 'logged out'})


class MeView(APIView):
    def get(self, request):
        if request.user.is_authenticated:
            return Response({'username': request.user.username, 'id': request.user.id})
        return Response({'error': 'Not authenticated'}, status=401)
