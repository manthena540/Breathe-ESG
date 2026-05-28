from django.db import models
from django.contrib.auth.models import User
from core.models import Organization


class IngestionJob(models.Model):
    """Tracks a single file upload / ingestion run."""

    SOURCE_SAP = 'sap'
    SOURCE_UTILITY = 'utility'
    SOURCE_TRAVEL = 'travel'
    SOURCE_CHOICES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility (Electricity)'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ingestion_jobs')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    uploaded_file = models.FileField(upload_to='uploads/%Y/%m/')
    original_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    uploaded_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_source_type_display()} — {self.original_filename} ({self.status})'


class EmissionRecord(models.Model):
    """
    One normalized emissions data point.

    Source tracking: ingestion_job tells you exactly which upload produced this row,
    source_row_id is the identifier from the original file (SAP doc number, meter ID, trip ID).
    raw_data preserves the original row verbatim so nothing is ever lost.
    """

    SCOPE_1 = '1'
    SCOPE_2 = '2'
    SCOPE_3 = '3'
    SCOPE_CHOICES = [(SCOPE_1, 'Scope 1'), (SCOPE_2, 'Scope 2'), (SCOPE_3, 'Scope 3')]

    # Scope 1 categories
    CAT_STATIONARY_COMBUSTION = 'stationary_combustion'
    CAT_MOBILE_COMBUSTION = 'mobile_combustion'
    # Scope 2 categories
    CAT_PURCHASED_ELECTRICITY = 'purchased_electricity'
    # Scope 3 categories
    CAT_BUSINESS_TRAVEL = 'business_travel'
    CAT_PURCHASED_GOODS = 'purchased_goods'

    CATEGORY_CHOICES = [
        (CAT_STATIONARY_COMBUSTION, 'Stationary Combustion'),
        (CAT_MOBILE_COMBUSTION, 'Mobile Combustion'),
        (CAT_PURCHASED_ELECTRICITY, 'Purchased Electricity'),
        (CAT_BUSINESS_TRAVEL, 'Business Travel'),
        (CAT_PURCHASED_GOODS, 'Purchased Goods & Services'),
    ]

    STATUS_PENDING = 'pending_review'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_FLAGGED = 'flagged'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_FLAGGED, 'Flagged'),
    ]

    # Tenant + source provenance
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='emission_records')
    ingestion_job = models.ForeignKey(IngestionJob, on_delete=models.CASCADE, related_name='records')
    source_row_id = models.CharField(max_length=255, blank=True)

    # Classification
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    activity_type = models.CharField(max_length=100)  # e.g. 'diesel', 'natural_gas', 'flight_economy'

    # Reporting period — billing periods don't align to calendar months
    period_start = models.DateField()
    period_end = models.DateField()

    # Raw quantity in source units (preserved for audit)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=50)  # e.g. 'liters', 'kWh', 'km'

    # Normalized quantity in standard unit per category
    quantity_normalized = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    normalized_unit = models.CharField(max_length=50, blank=True)

    # Calculated emissions (kg CO2e)
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    # Location / facility context
    facility = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=100, blank=True)

    # Original row preserved verbatim
    raw_data = models.JSONField()

    # Analyst review
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Suspicious flags raised during ingestion
    flags = models.JSONField(default=list, blank=True)

    # Locked after audit sign-off — no further edits allowed
    is_locked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-period_start', 'scope', 'category']

    def __str__(self):
        return f'{self.get_scope_display()} {self.activity_type} {self.quantity}{self.unit} [{self.status}]'


class AuditLog(models.Model):
    """Immutable record of every status change on an EmissionRecord."""

    ACTION_APPROVED = 'approved'
    ACTION_REJECTED = 'rejected'
    ACTION_FLAGGED = 'flagged'
    ACTION_EDITED = 'edited'
    ACTION_LOCKED = 'locked'
    ACTION_CHOICES = [
        (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'),
        (ACTION_FLAGGED, 'Flagged'),
        (ACTION_EDITED, 'Edited'),
        (ACTION_LOCKED, 'Locked'),
    ]

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='audit_logs')
    record = models.ForeignKey(EmissionRecord, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    before_state = models.JSONField()
    after_state = models.JSONField()
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.action} on record #{self.record_id} by {self.actor} at {self.timestamp}'
