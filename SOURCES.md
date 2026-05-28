# Sources — Research Notes and Sample Data Rationale

For each of the three data sources: what we researched, what we learned, what the sample data looks like, and what would break in a real deployment.

---

## 1. SAP — Fuel & Procurement

### What we researched

SAP data extraction for sustainability reporting is typically done via one of four mechanisms:
1. **SE16/MM60** — Table browser exports from purchasing tables (EKKO, EKPO for purchase orders; MSEG, MKPF for goods movements). Export to local file gives a flat CSV.
2. **SM35/Batch input** — Programmatic flat-file extraction.
3. **OData via SAP Gateway** — REST API, e.g., `/sap/opu/odata/sap/MM_PUR_PO_MAINT_V2_SRV/` for purchase orders.
4. **IDocs** — XML-based EDI documents used for inter-system communication (not analyst-facing).

**What a realistic export looks like:**
- EKKO (document header): document number, vendor, date, plant, company code, currency
- EKPO (document item): material group, material description, quantity, unit of measure, net value
- The join of EKKO + EKPO is what a typical "purchase order report" exports

**German column headers:** SAP systems running in German locale export column names like `Buchungsdatum` (posting date), `Werk` (plant), `Materialgruppe` (material group), `Menge` (quantity), `Mengeneinheit` (unit of measure). This is not edge-case behavior — it's the default for any SAP system installed for a German-language company or configured with German as the system language.

**SAP UoM codes:** SAP uses its own unit codes: `L` (liters), `KG` (kilograms), `M3` (cubic meters), `STK` or `EA` (each/units). These must be mapped to standard units before any calculation.

**Material groups:** SAP material groups (Warengruppe) are customer-configured. There is no universal "diesel = L001" mapping. A real deployment requires a client-provided mapping table from their material group codes to fuel types.

### What we learned

The biggest practical pain points in real SAP exports:
1. German vs English headers — handled via alias map
2. Decimal comma in German locale (`2.500,00` means 2500.00) — handled by stripping comma before decimal conversion
3. Date formats: `15.01.2024` (German) vs `01/15/2024` (US) vs `2024-01-15` (ISO) — handled via format list
4. Material groups are meaningless without a lookup table — we ship a sample mapping but flag unknowns
5. Credit memos appear as negative quantities — flagged as suspicious

### Sample data rationale

Our `sap_export.csv` uses mixed German/English headers to simulate a real-world export. The material groups (L001, FUEL_GAS, FUEL_PTR, FUEL_LPG) are plausible codes for a UK industrial company. Quantities are in realistic ranges for a mid-size manufacturer (1,800–6,200 liters per fuel delivery). One row uses German `Buchungsdatum` as the date header. One procurement row (PROC_GEN) has no quantity — simulating a service-type purchase order where quantity isn't meaningful.

### What would break in real deployment

1. **Material group mapping** — Client's material groups will not match our sample codes. Need a mapping spreadsheet from the client's SAP admin.
2. **Plant code resolution** — `PL01`, `PL02` mean nothing without a plant master data table. Need client to provide plant → location mapping.
3. **Decimal locale** — If the SAP system uses European decimal format (`1.234,56`), our parser will fail. Need to detect locale from the file or ask client.
4. **Missing fuel type data** — SAP doesn't distinguish diesel grade or biofuel blending ratio. The emission factor for B7 diesel (7% biodiesel) differs from pure diesel.
5. **Intercompany transactions** — Fuel transfers between subsidiaries appear as procurement. Need to flag and exclude.

---

## 2. Utility Data — Electricity

### What we researched

Utility data formats in the UK:
- **Half-hourly (HH) data** — Larger commercial premises have half-hourly metering. Data is available from the utility as 48 readings per day. UK portal providers: Stark, Utilitrac, Openenergi.
- **Smart meter CSV export** — Most UK utilities (OVO, Octopus, British Gas Business, EDF) offer a "download my data" CSV from their business portal.
- **Green Button (US)** — XML/CSV standard for utility data in the US. Well-standardized.
- **ESME API** — UK smart meter data service. Requires enrollment and is not yet universally available.

**Billing period structure:** UK commercial electricity bills typically cover a billing period (e.g., 28–35 days) that does not align with calendar months. The bill date is when the invoice is issued, not the period end. Meter readings are taken at period start and end.

**Units:** kWh (most sites), MWh (very large sites). Utility portals sometimes export in MWh without labeling it clearly — we normalize to kWh internally.

**Tariff codes:** HH-HALFHOUR (half-hourly metered large commercial), SME-BUSINESS (small/medium enterprise), HV-INDUSTRIAL (high-voltage industrial). These appear in utility exports and are useful context but don't affect the emission calculation directly.

**Emission factors:** UK National Grid publishes annual emission factors. DEFRA provides the standard conversion factors used for GHG reporting:
- UK grid 2023: 0.207 kg CO2e/kWh
- UK grid 2022: 0.193 kg CO2e/kWh (year-on-year change due to renewable mix)

A market-based approach uses the supplier tariff's fuel mix disclosure instead of the grid average — relevant for clients with renewable tariffs or PPAs.

### What we learned

1. Billing periods are rarely 30/31 days. A "January bill" commonly covers Dec 14 – Jan 13.
2. Zero-read periods happen. A meter reading of 0 kWh doesn't mean no consumption — it may mean the meter wasn't read. Must flag, not silently accept.
3. Multiple meters per site. The Edinburgh Data Centre in our sample has a separate account from the London HQ, as real enterprise clients have.
4. MWh vs kWh confusion. Our Leeds Factory row exports in MWh; the parser detects and converts.

### Sample data rationale

Our `utility_export.csv` models a multi-site UK enterprise with:
- London HQ on half-hourly metering (billing period ~30 days, not calendar-aligned)
- Manchester office on SME tariff (calendar month billing)
- Birmingham warehouse on half-hourly (billing starts Dec 28, not Jan 1)
- Edinburgh data centre with very high consumption (215 MWh/month — realistic for a mid-size DC)
- Bristol Lab with a zero-read month (testing flagging logic)
- Leeds Factory billing in MWh (testing unit conversion)

### What would break in real deployment

1. **PDF bills** — Many clients have PDF bills, not portal CSVs. PDF parsing is fragile and not implemented.
2. **Market-based emission factors** — Clients with renewable tariffs or REGOs should use 0 kg CO2e/kWh (market-based). We default to location-based. Need client to supply tariff emission factors.
3. **Annual reporting** — DEFRA factors change annually. A bill from Dec 2023 and a bill from Jan 2024 may need different factors. We apply a single factor.
4. **Transmission & distribution losses** — Scope 2 includes T&D losses. Our factors include T&D (DEFRA factors do); a client using a raw generation factor would undercount.
5. **Multiple fuel types** — Some sites have gas and electricity from the same utility portal. Our parser only handles electricity.

---

## 3. Corporate Travel — Concur/Navan

### What we researched

**Concur Expense Extract:** The standard report in SAP Concur for extracting travel expense data. Available as a scheduled export to SFTP or manual CSV download from the Concur Insight reporting module. Columns include: expense type, amount, merchant, dates, origin/destination for travel.

**Concur Travel Extract:** A separate report for booked travel (not expenses). Contains booking-level data including cabin class, fare basis, actual flight numbers.

**Navan (formerly TripActions):** Modern corporate travel platform with a REST API. Returns JSON with similar fields. Also offers CSV exports.

**GHG Protocol Scope 3 Category 6:** Business travel includes: air travel, rail, car rental, hotel stays, ground transport. DEFRA 2023 factors cover all of these.

**IATA distance vs actual routing:** A London (LHR) → New York (JFK) booking may route through Amsterdam on a codeshare. The actual distance flown differs from great-circle. ICAO provides routing factors; our implementation uses great-circle as a conservative approximation.

**Radiative forcing:** Aviation emissions have a warming effect from contrails and NOx beyond CO2 alone. DEFRA 2023 includes a radiative forcing index (RFI) of approximately 1.9x applied to the CO2 factor. Our factors include this uplift.

### What we learned

1. **Cabin class matters enormously.** Business class on a long-haul flight has ~2.8x the CO2e of economy (DEFRA 2023). Defaulting unknown bookings to economy systematically undercounts emissions for senior staff who travel business class.

2. **Concur often doesn't record distance.** The export gives origin/destination airports but not km flown. We compute great-circle distance from IATA codes. For ~30 major hubs, this works. For regional airports or non-standard codes, it fails.

3. **Hotel emission factors are approximate.** We use 31 kg CO2e/room-night (DEFRA 2023 UK average). This varies enormously: a London 5-star hotel may be 80 kg/night; a budget hotel with a renewable tariff may be 10 kg/night. HCMI (Hotel Carbon Measurement Initiative) provides hotel-specific factors but requires enrollment.

4. **Ground transport is often uncategorized.** Concur expense categories include "taxi", "ground transport", "car rental" but classification is inconsistent. We match on partial string; unmatched types default to taxi factor.

### Sample data rationale

Our `travel_export.csv` is modeled on a UK company with international business travel. We included:
- Long-haul flights (LHR→JFK, LHR→SIN, LHR→BOM, LHR→BLR) with varying cabin classes to demonstrate factor differences
- Short-haul European flights (LHR→CDG, LHR→AMS, LHR→FRA) which have higher per-km factors than long-haul
- Hotel stays paired with flights to match real booking patterns
- One CEO booking in first class (TRP-10038) to demonstrate the factor difference
- Ground transport (taxi, car rental) to test the ground parser
- Rail (SNCF) to test rail factor
- Intra-regional flight (SIN→HKG) to test non-LHR origin routing

The employee IDs are anonymized (EMP-0341, etc.) — a real deployment would hash or tokenize PII.

### What would break in real deployment

1. **Unknown airport codes** — Our IATA coordinate table covers 30 hubs. A Tier-2 city airport (e.g., BHX for Birmingham, UK) would cause a parse error and require adding to the coordinate table.
2. **Codeshare routing** — LHR→JFK operated by AA on a BA codeshare actually flies a different route than BA-operated service. We ignore this; real implementations may use flight number lookup.
3. **PII in raw_data** — Employee IDs and trip details are stored in `raw_data JSON`. A GDPR-compliant deployment needs a PII handling policy.
4. **Multi-leg trips** — A single booking may have 3 legs (e.g., LHR→DXB→BOM). Our sample treats each row as one leg. Concur may combine legs into one expense record.
5. **Carbon offsetting** — Some clients offset business travel. The offset should reduce Scope 3, but only if the offset is verified (Gold Standard, VCS). We don't handle this.
