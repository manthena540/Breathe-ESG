"""
Management command: python manage.py seed

Creates a demo organization, analyst user, and loads all three sample CSV files
so the app is immediately usable after deploy.
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Organization
from ingestion.models import IngestionJob, EmissionRecord
from ingestion.parsers import sap, utility, travel

SAMPLE_DIR = Path(__file__).resolve().parents[4] / 'sample_data'

SOURCES = [
    ('sap', 'sap_export.csv', sap.parse),
    ('utility', 'utility_export.csv', utility.parse),
    ('travel', 'travel_export.csv', travel.parse),
]


class Command(BaseCommand):
    help = 'Seed database with demo organization and sample emission data'

    def handle(self, *args, **options):
        # Create org
        org, created = Organization.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'ACME Corporation'}
        )
        self.stdout.write(f'{"Created" if created else "Found"} org: {org.name}')

        # Create analyst user
        if not User.objects.filter(username='analyst').exists():
            User.objects.create_user('analyst', 'analyst@acme.com', 'analyst123', first_name='Demo', last_name='Analyst')
            self.stdout.write('Created user: analyst / analyst123')

        # Create admin user
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@acme.com', 'admin123')
            self.stdout.write('Created superuser: admin / admin123')

        uploader = User.objects.get(username='analyst')

        for source_type, filename, parse_fn in SOURCES:
            filepath = SAMPLE_DIR / filename
            if not filepath.exists():
                self.stdout.write(self.style.WARNING(f'  Sample file not found: {filepath}'))
                continue

            content = filepath.read_bytes()
            records_data, errors = parse_fn(content)

            job = IngestionJob.objects.create(
                organization=org,
                source_type=source_type,
                uploaded_file='',
                original_filename=filename,
                status=IngestionJob.STATUS_COMPLETED,
                uploaded_by=uploader,
                completed_at=timezone.now(),
                row_count=len(records_data),
                error_count=len(errors),
                error_log=errors,
            )

            for rd in records_data:
                EmissionRecord.objects.create(organization=org, ingestion_job=job, **rd)

            self.stdout.write(
                self.style.SUCCESS(
                    f'  {source_type}: {len(records_data)} records loaded ({len(errors)} errors)'
                )
            )

        self.stdout.write(self.style.SUCCESS('\nSeed complete. Login: analyst / analyst123'))
