# Decisions

Every non-obvious choice made during design and implementation.

---

## SAP Export Format: Flat-File CSV (OData-style)

**Chose:** SM35/SE16-style flat-file CSV with optional German column headers

**Considered:**
- IDoc — XML-based EDI format used for inter-system messaging. Not human-facing; requires an EDI middleware layer. Not what a sustainability analyst would hand you.
- OData service — REST-based SAP Gateway API. Requires SAP Gateway configuration, OAuth, and system-to-system connectivity. Not realistic for a prototype and not what "SAP export" means to most sustainability teams.
- BAPI — RFC-based function module calls. Requires SAP GUI or JCo connector. No.
- **Flat-file CSV from SE16/SM35** — This is what actually happens. A finance or sustainability team member opens SAP, runs a report (ME2M for purchase orders, MB51 for goods movements), exports to spreadsheet, and sends it to you. The column headers may be German depending on SAP system locale.

**Why German headers matter:** SAP system language is configurable. A UK subsidiary running an SAP system set to German locale will export `Buchungsdatum` not `BookingDate`. Any parser that only handles English headers will silently fail for ~30% of real SAP exports. Our parser maps both via an alias table.

**What I'd ask the PM:** Which SAP module does this client use for fuel tracking — MM (Materials Management, purchase orders) or FI-CO (actual goods consumption)? This determines whether we're parsing `EKKO/EKPO` (PO data) or `MSEG` (goods movement). They have different schemas.

---

## Utility Data: Portal CSV Export

**Chose:** CSV export from utility portal

**Considered:**
- PDF bill parsing — Most utility bills in the UK arrive as PDFs. Parsing PDFs with consistent structure is achievable but fragile; layout changes break the parser. PDF extraction would require pdfplumber or AWS Textract and adds significant complexity for uncertain reliability.
- Utility API — Green Button (US) and ESME APIs (UK smart meters) exist, but: (a) enterprise accounts rarely have programmatic access enabled, (b) OAuth flows vary by utility, (c) this requires ongoing API credentials management. Unrealistic for a prototype.
- **Portal CSV** — Every UK and EU utility portal (OVO, EDF, Octopus, National Grid Portal) offers a data download. The format is CSV with meter ID, billing period, and consumption. This is what a facilities manager actually exports. It's structured enough to parse reliably.

**Billing period alignment:** Bills do not align with calendar months. A smart meter billing period may be Dec 15 – Jan 14. We store `period_start` and `period_end` as separate date fields rather than forcing a `month` integer. This prevents the systematic error of attributing 45 days of consumption to January.

**Emission factor:** We apply a grid-average emission factor per country/region (UK: 0.207 kg CO2e/kWh, DEFRA 2023). A real deployment would use location-based (regional grid mix) or market-based (supplier tariff, REGOs) factors. The field `emission_factor_override` allows customers to supply their own factor.

**What I'd ask the PM:** Does this client have renewable energy certificates (REGOs/RECs) that would allow market-based accounting for Scope 2? This changes the emission factor from ~0.207 to ~0 for certified renewable supply.

---

## Corporate Travel: Concur Expense Extract Format

**Chose:** Concur standard Expense Extract CSV

**Considered:**
- Navan API — Modern, well-documented. But requires OAuth enterprise credentials and returns JSON. For a prototype, CSV upload is more practical and easier to demonstrate.
- SAP Concur API — REST API available, but again requires OAuth and enterprise enrollment. The Expense Extract report (available as a scheduled export) is what sustainability teams actually receive.
- **Concur Expense Extract** — This is the standard report that Concur customers export. It's a CSV with columns for trip ID, travel type, origin/destination, cost, etc. Many clients already schedule this weekly.

**Airport code → distance:** Concur does not always provide distance. We calculate great-circle distance from IATA airport codes using the Haversine formula. We ship coordinates for ~30 major hubs. Missing airport codes produce a parse error and a flag rather than silently using 0 km.

**Cabin class:** Economy, business, and first class have different emission factors (DEFRA 2023: economy 0.155 kg CO2e/km, business 0.429, first 0.609). We default to economy if cabin class is unspecified and flag the record.

**Hotels:** We use a per-room-night factor (31 kg CO2e/night, DEFRA 2023 average). This is a coarse approximation; a real deployment would use hotel-specific data from the Hotel Carbon Measurement Initiative (HCMI) if available.

**What I'd ask the PM:** Does the client use Concur or a different platform (Navan, TripActions, Egencia)? And do they have the SAP Concur Expense Extract report already scheduled, or would we need to set it up?

---

## Ingestion Mechanism: File Upload (not API pull)

**Chose:** File upload (CSV drag-and-drop / form upload)

**Reasoning:** A pull-based integration (scheduled API calls to SAP, utility APIs, Concur) requires:
1. Stable API credentials stored securely
2. OAuth flows or API key management
3. Ongoing connectivity and error handling
4. Client IT involvement to grant access

For onboarding a new enterprise client in a prototype context, file upload is both more realistic (sustainability teams often manually export data) and more demonstrable. It also lets the client control what data they share, which matters for enterprise procurement.

**What this means for production:** Pull integrations would be the ideal end state. The `IngestionJob` and parser architecture already supports this — a pull job would just call `parse()` on fetched bytes rather than uploaded bytes.

---

## Authentication: Session-based (not JWT)

**Chose:** Django session authentication

**Reasoning:** For an internal analyst tool, session auth is appropriate. JWT would require refresh token management, a separate auth service, or third-party library. The React frontend uses `withCredentials: true` to send the session cookie. This is simpler and secure for a same-domain or proxied deployment.

**What I'd ask the PM:** Does the client have an SSO (Okta, Azure AD) requirement? Most enterprise clients do. Adding SAML or OIDC would be the first production requirement.

---

## Emission Factors: Hardcoded in Parsers

**Chose:** Hardcoded DEFRA 2023 / IPCC AR5 factors in parser code

**Why not a database table?**
A factor table requires: versioning (which year's factors apply?), source attribution, and a UI for managing them. That's a significant feature in itself. For the prototype, hardcoded constants with clear source comments are honest and maintainable.

**The real problem:** Emission factors change annually. DEFRA publishes new conversion factors every June. A factor that was correct in 2023 is wrong in 2024. In production, factors would need a versioned table keyed by (activity_type, unit, reporting_year, source).

---

## Scope 3 Purchased Goods: Spend-based Approximation

For SAP procurement rows that aren't fuel (material group doesn't map to a fuel type), we classify them as Scope 3 Category 1 (Purchased Goods & Services) but do not calculate CO2e. Spend-based emission factors (e.g., EXIOBASE) require the spend amount in a consistent currency and a MRIO model — well outside prototype scope. We flag these records as requiring manual factor assignment.

---

## What I'd ask the PM

1. Which SAP module (MM vs FI-CO) for fuel — determines schema
2. Renewable energy certificates for Scope 2 market-based accounting?
3. SSO requirement for enterprise login?
4. Which Concur report is already scheduled for export?
5. Are there multiple reporting periods in flight (FY2023 restatement + FY2024 current)?
6. Will the same facility appear in both SAP and utility data? How do we match them? (Plant code vs meter address)
7. What's the reporting boundary — operational control or equity share?
