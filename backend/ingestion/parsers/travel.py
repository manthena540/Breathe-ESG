"""
Corporate Travel CSV Parser (Concur Expense Extract format — Scope 3, Category 6)

Based on Concur's standard Expense Extract (SAE) report. Handles flights, hotels,
ground transport. Airport codes → distances calculated via great-circle approximation
when distance is not provided directly. Different transport modes have different
emission factors (economy vs business class, etc.).
"""

import csv
import io
import math
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

HEADER_ALIASES = {
    'Trip ID': 'trip_id',
    'TripID': 'trip_id',
    'Report ID': 'trip_id',
    'Employee ID': 'employee_id',
    'EmployeeID': 'employee_id',
    'Department': 'department',
    'Travel Type': 'travel_type',
    'TravelType': 'travel_type',
    'Category': 'travel_type',
    'Origin': 'origin',
    'Destination': 'destination',
    'Departure Date': 'departure_date',
    'DepartureDate': 'departure_date',
    'Return Date': 'return_date',
    'ReturnDate': 'return_date',
    'Distance (km)': 'distance_km',
    'Distance': 'distance_km',
    'DistanceKm': 'distance_km',
    'Origin Airport': 'origin_airport',
    'OriginAirport': 'origin_airport',
    'Destination Airport': 'destination_airport',
    'DestinationAirport': 'destination_airport',
    'Class': 'cabin_class',
    'CabinClass': 'cabin_class',
    'Nights': 'hotel_nights',
    'HotelNights': 'hotel_nights',
    'Hotel Name': 'hotel_name',
    'HotelName': 'hotel_name',
    'Country': 'country',
    'Cost': 'cost',
    'Amount': 'cost',
    'Currency': 'currency',
    'Vendor': 'vendor',
}

# IATA airport code → (lat, lon) for great-circle distance
# A real deployment would use a full airport database; we include key hubs
AIRPORT_COORDS = {
    'LHR': (51.4775, -0.4614), 'LGW': (51.1481, -0.1903),
    'JFK': (40.6413, -73.7781), 'LAX': (33.9425, -118.4081),
    'ORD': (41.9742, -87.9073), 'SFO': (37.6213, -122.3790),
    'DXB': (25.2528, 55.3644), 'SIN': (1.3644, 103.9915),
    'HKG': (22.3080, 113.9185), 'NRT': (35.7720, 140.3929),
    'CDG': (49.0097, 2.5479), 'AMS': (52.3086, 4.7639),
    'FRA': (50.0379, 8.5622), 'MUC': (48.3538, 11.7861),
    'BOM': (19.0896, 72.8656), 'DEL': (28.5562, 77.1000),
    'BLR': (13.1979, 77.7063), 'MAA': (12.9941, 80.1709),
    'HYD': (17.2313, 78.4298), 'SYD': (-33.9461, 151.1772),
    'DFW': (32.8998, -97.0403), 'MIA': (25.7959, -80.2870),
    'BOS': (42.3656, -71.0096), 'SEA': (47.4502, -122.3088),
}

# kg CO2e per passenger-km (DEFRA 2023 / ICAO methodology)
FLIGHT_FACTORS = {
    'economy': Decimal('0.15530'),
    'business': Decimal('0.42884'),
    'first': Decimal('0.60880'),
    'premium_economy': Decimal('0.21290'),
    'unknown': Decimal('0.15530'),  # default to economy
}

# kg CO2e per passenger-km for ground transport
GROUND_FACTORS = {
    'taxi': Decimal('0.14940'),
    'car_rental': Decimal('0.16800'),
    'rail': Decimal('0.03549'),
    'bus': Decimal('0.02710'),
    'ferry': Decimal('0.11370'),
    'unknown': Decimal('0.14940'),
}

# kg CO2e per hotel room night (DEFRA 2023 average, varies by country)
HOTEL_FACTOR = Decimal('31.0')


def _parse_date(val: str) -> date | None:
    val = (val or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d.%m.%Y'):
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


def _great_circle_km(iata1: str, iata2: str) -> Decimal | None:
    c1 = AIRPORT_COORDS.get(iata1.upper())
    c2 = AIRPORT_COORDS.get(iata2.upper())
    if not c1 or not c2:
        return None
    lat1, lon1 = math.radians(c1[0]), math.radians(c1[1])
    lat2, lon2 = math.radians(c2[0]), math.radians(c2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return Decimal(str(round(c * 6371, 1)))


def _normalize_headers(raw_headers: list[str]) -> dict[str, str]:
    return {h: HEADER_ALIASES.get(h.strip(), h.strip().lower().replace(' ', '_')) for h in raw_headers}


def parse(file_content: bytes) -> tuple[list[dict], list[str]]:
    text = file_content.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(text))
    header_map = _normalize_headers(reader.fieldnames or [])

    records = []
    errors = []

    for i, row in enumerate(reader, start=2):
        nr = {header_map.get(k, k): v for k, v in row.items()}
        flags = []

        trip_id = nr.get('trip_id', '').strip() or f'row_{i}'
        travel_type = (nr.get('travel_type', '') or '').strip().lower()
        departure_date_raw = nr.get('departure_date', '')

        departure_date = _parse_date(departure_date_raw)
        if not departure_date:
            errors.append(f'Row {i}: unparseable departure_date "{departure_date_raw}"')
            continue

        return_date = _parse_date(nr.get('return_date', '') or '') or departure_date

        if travel_type in ('flight', 'air', 'airline', 'aviation', ''):
            origin_code = nr.get('origin_airport', nr.get('origin', '')).strip().upper()
            dest_code = nr.get('destination_airport', nr.get('destination', '')).strip().upper()
            cabin = (nr.get('cabin_class', '') or '').strip().lower() or 'economy'

            distance = _parse_decimal(nr.get('distance_km', '') or '')
            if not distance:
                distance = _great_circle_km(origin_code, dest_code)
                if distance:
                    flags.append(f'Distance estimated from airport codes {origin_code}→{dest_code}: {distance} km')
                else:
                    flags.append(f'Cannot resolve distance — unknown airport code(s): {origin_code}/{dest_code}')
                    errors.append(f'Row {i}: cannot compute distance for flight {origin_code}→{dest_code}')
                    continue

            factor = FLIGHT_FACTORS.get(cabin, FLIGHT_FACTORS['unknown'])
            if cabin not in FLIGHT_FACTORS:
                flags.append(f'Unknown cabin class "{cabin}" — defaulting to economy factor')

            co2e_kg = distance * factor

            records.append({
                'source_row_id': trip_id,
                'scope': '3',
                'category': 'business_travel',
                'activity_type': f'flight_{cabin}',
                'period_start': departure_date,
                'period_end': return_date,
                'quantity': distance,
                'unit': 'km',
                'quantity_normalized': distance,
                'normalized_unit': 'km',
                'co2e_kg': co2e_kg,
                'facility': '',
                'country': nr.get('country', '').strip(),
                'raw_data': dict(row),
                'flags': flags,
            })

        elif travel_type in ('hotel', 'accommodation', 'lodging'):
            nights = _parse_decimal(nr.get('hotel_nights', '') or '')
            if not nights or nights <= 0:
                flags.append('No hotel nights specified — assuming 1')
                nights = Decimal('1')

            co2e_kg = nights * HOTEL_FACTOR

            records.append({
                'source_row_id': trip_id,
                'scope': '3',
                'category': 'business_travel',
                'activity_type': 'hotel_stay',
                'period_start': departure_date,
                'period_end': return_date,
                'quantity': nights,
                'unit': 'nights',
                'quantity_normalized': nights,
                'normalized_unit': 'nights',
                'co2e_kg': co2e_kg,
                'facility': nr.get('hotel_name', '').strip(),
                'country': nr.get('country', '').strip(),
                'raw_data': dict(row),
                'flags': flags,
            })

        else:
            # Ground transport
            distance = _parse_decimal(nr.get('distance_km', '') or '')
            if not distance:
                flags.append('No distance provided for ground transport — cannot compute emissions')
                distance = Decimal('0')

            transport_key = 'unknown'
            for key in GROUND_FACTORS:
                if key in travel_type:
                    transport_key = key
                    break

            factor = GROUND_FACTORS[transport_key]
            co2e_kg = distance * factor

            records.append({
                'source_row_id': trip_id,
                'scope': '3',
                'category': 'business_travel',
                'activity_type': f'ground_{transport_key}',
                'period_start': departure_date,
                'period_end': return_date,
                'quantity': distance,
                'unit': 'km',
                'quantity_normalized': distance,
                'normalized_unit': 'km',
                'co2e_kg': co2e_kg,
                'facility': '',
                'country': nr.get('country', '').strip(),
                'raw_data': dict(row),
                'flags': flags,
            })

    return records, errors
