"""
SAP Flat-File CSV Parser (OData-style export)

Real SAP exports via OData or SM35/SE16 flat file. Columns reflect typical EKPO (purchasing
document item) and EKKO (purchasing document header) join with material master (MARA).
German column headers handled via alias map. Dates in DD.MM.YYYY format.
Units in SAP UoM codes (L, KG, M3, STK, etc.).
"""

import csv
import io
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

# Map German SAP column headers -> normalized field names
HEADER_ALIASES = {
    'Buchungsdatum': 'posting_date',
    'BookingDate': 'posting_date',
    'Belegdatum': 'document_date',
    'DocumentDate': 'document_date',
    'Belegnummer': 'document_number',
    'DocumentNumber': 'document_number',
    'Menge': 'quantity',
    'Quantity': 'quantity',
    'Mengeneinheit': 'unit',
    'UnitOfMeasure': 'unit',
    'Materialgruppe': 'material_group',
    'MaterialGroup': 'material_group',
    'Werk': 'plant',
    'Plant': 'plant',
    'Nettowert': 'net_value',
    'NetValue': 'net_value',
    'Waehrung': 'currency',
    'Currency': 'currency',
    'Materialbeschreibung': 'material_description',
    'MaterialDescription': 'material_description',
    'Lieferant': 'vendor',
    'Vendor': 'vendor',
    'Kostenstelle': 'cost_center',
    'CostCenter': 'cost_center',
}

# SAP UoM → standard unit
UOM_MAP = {
    'L': 'liters',
    'LTR': 'liters',
    'GAL': 'gallons_us',
    'KG': 'kg',
    'G': 'grams',
    'T': 'metric_tons',
    'M3': 'cubic_meters',
    'STK': 'units',
    'EA': 'units',
    'KWH': 'kWh',
    'MWH': 'MWh',
}

# Material group → activity type + scope/category
MATERIAL_GROUP_MAP = {
    '001': ('diesel', '1', 'mobile_combustion'),
    'L001': ('diesel', '1', 'mobile_combustion'),
    'FUEL_DSL': ('diesel', '1', 'mobile_combustion'),
    '002': ('petrol', '1', 'mobile_combustion'),
    'FUEL_PTR': ('petrol', '1', 'mobile_combustion'),
    '003': ('natural_gas', '1', 'stationary_combustion'),
    'FUEL_GAS': ('natural_gas', '1', 'stationary_combustion'),
    '004': ('lpg', '1', 'stationary_combustion'),
    'FUEL_LPG': ('lpg', '1', 'stationary_combustion'),
    'PROC_GEN': ('purchased_goods_general', '3', 'purchased_goods'),
    'PROC_CHM': ('purchased_chemicals', '3', 'purchased_goods'),
}

# Emission factors kg CO2e per liter / kg (simplified IPCC AR5 values)
EMISSION_FACTORS = {
    'diesel': {'unit': 'liters', 'factor': Decimal('2.6391')},
    'petrol': {'unit': 'liters', 'factor': Decimal('2.3120')},
    'natural_gas': {'unit': 'cubic_meters', 'factor': Decimal('2.0400')},
    'lpg': {'unit': 'liters', 'factor': Decimal('1.5654')},
}


def _parse_date(val: str) -> date | None:
    val = (val or '').strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val: str) -> Decimal | None:
    val = (val or '').strip().replace(',', '.')
    try:
        return Decimal(val)
    except InvalidOperation:
        return None


def _normalize_headers(raw_headers: list[str]) -> dict[str, str]:
    return {h: HEADER_ALIASES.get(h.strip(), h.strip()) for h in raw_headers}


def parse(file_content: bytes) -> tuple[list[dict], list[str]]:
    """
    Returns (records, errors).
    records: list of normalized dicts ready for EmissionRecord creation.
    errors: list of human-readable parse error strings.
    """
    text = file_content.decode('utf-8-sig')  # strip BOM if present
    reader = csv.DictReader(io.StringIO(text))
    header_map = _normalize_headers(reader.fieldnames or [])

    records = []
    errors = []

    for i, row in enumerate(reader, start=2):
        normalized_row = {header_map.get(k, k): v for k, v in row.items()}
        flags = []

        doc_number = normalized_row.get('document_number', '').strip()
        plant = normalized_row.get('plant', '').strip()
        material_group = normalized_row.get('material_group', '').strip()
        quantity_raw = normalized_row.get('quantity', '')
        unit_raw = normalized_row.get('unit', '').strip().upper()
        posting_date_raw = normalized_row.get('posting_date', '')

        quantity = _parse_decimal(quantity_raw)
        if quantity is None:
            errors.append(f'Row {i}: unparseable quantity "{quantity_raw}"')
            continue

        posting_date = _parse_date(posting_date_raw)
        if posting_date is None:
            errors.append(f'Row {i}: unparseable date "{posting_date_raw}"')
            continue

        unit = UOM_MAP.get(unit_raw, unit_raw.lower())

        activity_type, scope, category = MATERIAL_GROUP_MAP.get(
            material_group, ('unknown_procurement', '3', 'purchased_goods')
        )
        if activity_type == 'unknown_procurement':
            flags.append(f'Unknown material group "{material_group}" — defaulted to Scope 3 purchased goods')

        if quantity < 0:
            flags.append('Negative quantity — possible credit memo')
        if quantity > 100000:
            flags.append('Unusually large quantity — verify unit')

        ef = EMISSION_FACTORS.get(activity_type)
        co2e_kg = None
        if ef and unit == ef['unit']:
            co2e_kg = quantity * ef['factor']
        elif ef:
            flags.append(f'Unit mismatch: expected {ef["unit"]} for {activity_type}, got {unit}')

        records.append({
            'source_row_id': doc_number or f'row_{i}',
            'scope': scope,
            'category': category,
            'activity_type': activity_type,
            'period_start': posting_date,
            'period_end': posting_date,
            'quantity': quantity,
            'unit': unit,
            'quantity_normalized': quantity,
            'normalized_unit': unit,
            'co2e_kg': co2e_kg,
            'facility': plant,
            'country': '',
            'raw_data': dict(row),
            'flags': flags,
        })

    return records, errors
