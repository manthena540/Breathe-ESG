"""
Utility Portal CSV Export Parser (Electricity — Scope 2)

Based on typical utility portal exports (e.g., Enel, EDF, National Grid portals).
Billing periods don't align with calendar months — a January bill may cover
Dec 15 – Jan 14. We preserve both period_start and period_end exactly.
Meter readings come in kWh or MWh; tariff structures vary by utility.
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation


HEADER_ALIASES = {
    'Account Number': 'account_number',
    'AccountNumber': 'account_number',
    'Meter ID': 'meter_id',
    'MeterID': 'meter_id',
    'Meter Number': 'meter_id',
    'Site Name': 'site_name',
    'SiteName': 'site_name',
    'Facility': 'site_name',
    'Bill Period Start': 'period_start',
    'PeriodStart': 'period_start',
    'BillingPeriodStart': 'period_start',
    'Bill Period End': 'period_end',
    'PeriodEnd': 'period_end',
    'BillingPeriodEnd': 'period_end',
    'Usage': 'usage',
    'Consumption': 'usage',
    'kWh': 'usage',
    'Unit': 'unit',
    'Units': 'unit',
    'UOM': 'unit',
    'Tariff': 'tariff',
    'Rate Code': 'tariff',
    'RateCode': 'tariff',
    'Cost': 'cost',
    'Amount': 'cost',
    'Total Amount': 'cost',
    'Currency': 'currency',
    'Address': 'address',
    'Country': 'country',
    'Grid Region': 'grid_region',
    'GridRegion': 'grid_region',
    'Emission Factor': 'emission_factor_override',
    'CO2e Factor': 'emission_factor_override',
}

# UK grid: 0.207 kg CO2e/kWh (DEFRA 2023), US avg: 0.386 kg CO2e/kWh (EPA 2023)
# We default to UK; a real deployment would look this up per grid region / year
GRID_EMISSION_FACTORS = {
    'UK': Decimal('0.2070'),
    'US': Decimal('0.3860'),
    'EU': Decimal('0.2760'),
    'IN': Decimal('0.7080'),
    'DEFAULT': Decimal('0.2330'),
}


def _parse_date(val: str) -> date | None:
    val = (val or '').strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%m/%d/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val: str) -> Decimal | None:
    val = (val or '').strip().replace(',', '')
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def _normalize_headers(raw_headers: list[str]) -> dict[str, str]:
    return {h: HEADER_ALIASES.get(h.strip(), h.strip().lower().replace(' ', '_')) for h in raw_headers}


def _to_kwh(quantity: Decimal, unit: str) -> Decimal:
    unit = unit.strip().lower()
    if unit in ('kwh', 'kw h'):
        return quantity
    if unit in ('mwh', 'mw h'):
        return quantity * 1000
    if unit in ('gwh', 'gw h'):
        return quantity * 1_000_000
    return quantity  # assume kWh if unrecognized


def parse(file_content: bytes) -> tuple[list[dict], list[str]]:
    text = file_content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    header_map = _normalize_headers(reader.fieldnames or [])

    records = []
    errors = []

    for i, row in enumerate(reader, start=2):
        normalized_row = {header_map.get(k, k): v for k, v in row.items()}
        flags = []

        meter_id = normalized_row.get('meter_id', '').strip()
        site_name = normalized_row.get('site_name', '').strip()
        usage_raw = normalized_row.get('usage', '')
        unit_raw = normalized_row.get('unit', 'kWh').strip()
        period_start_raw = normalized_row.get('period_start', '')
        period_end_raw = normalized_row.get('period_end', '')
        country = normalized_row.get('country', '').strip().upper()
        grid_region = normalized_row.get('grid_region', '').strip().upper()
        ef_override_raw = normalized_row.get('emission_factor_override', '').strip()

        usage = _parse_decimal(usage_raw)
        if usage is None:
            errors.append(f'Row {i}: unparseable usage "{usage_raw}"')
            continue

        period_start = _parse_date(period_start_raw)
        period_end = _parse_date(period_end_raw)
        if not period_start:
            errors.append(f'Row {i}: unparseable period_start "{period_start_raw}"')
            continue
        if not period_end:
            errors.append(f'Row {i}: unparseable period_end "{period_end_raw}"')
            continue

        usage_kwh = _to_kwh(usage, unit_raw)

        # Billing period sanity check
        days = (period_end - period_start).days
        if days < 1:
            flags.append('period_end before period_start')
        elif days > 93:
            flags.append(f'Billing period {days} days — unusually long, verify')

        if usage_kwh <= 0:
            flags.append('Zero or negative usage — possible zero-read or credit')
        if usage_kwh > 500_000:
            flags.append('Usage >500 MWh in one period — verify meter or unit')

        # Resolve emission factor
        ef_override = _parse_decimal(ef_override_raw)
        if ef_override:
            ef = ef_override
            flags.append(f'Using customer-supplied emission factor {ef} kg CO2e/kWh')
        else:
            region_key = grid_region or country or 'DEFAULT'
            ef = GRID_EMISSION_FACTORS.get(region_key, GRID_EMISSION_FACTORS['DEFAULT'])
            if region_key == 'DEFAULT':
                flags.append('No grid region specified — using global average emission factor')

        co2e_kg = usage_kwh * ef

        records.append({
            'source_row_id': meter_id or f'row_{i}',
            'scope': '2',
            'category': 'purchased_electricity',
            'activity_type': 'grid_electricity',
            'period_start': period_start,
            'period_end': period_end,
            'quantity': usage,
            'unit': unit_raw,
            'quantity_normalized': usage_kwh,
            'normalized_unit': 'kWh',
            'co2e_kg': co2e_kg,
            'facility': site_name,
            'country': country,
            'raw_data': dict(row),
            'flags': flags,
        })

    return records, errors
