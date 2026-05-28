# Tradeoffs — What We Deliberately Did Not Build

Three things we chose not to build and exactly why.

---

## 1. Emission Factor Versioning

**What it is:** A database table of emission factors keyed by `(activity_type, unit, reporting_year, region, source)`, with a UI to manage them, and logic to automatically apply the correct year's factor when calculating CO2e.

**Why we didn't build it:**
DEFRA publishes new conversion factors every June. A full factor versioning system requires:
- A `EmissionFactor` model with effective date ranges
- A factor resolution algorithm (which year applies to a record with period_start in Dec 2023?)
- An admin interface for non-engineers to update factors without a code deploy
- Re-calculation logic: when a factor changes, do we recalculate all historical records, or only new ones?

The re-calculation question is genuinely hard. If we recalculate, do approved records get automatically re-approved? If we don't, we have a permanent discrepancy between records calculated under different factor vintages.

**What we did instead:** Hardcoded DEFRA 2023 factors in parser code with clear source comments. The `quantity_normalized` field is factor-independent, so a future re-calculation just multiplies by the new factor — no re-parsing required.

**Cost of this tradeoff:** Any records ingested with a wrong emission factor will show incorrect CO2e. For the prototype, this is acceptable. For production: this is the first thing to build after the MVP.

---

## 2. Pull-Based API Integrations

**What it is:** Scheduled API calls to SAP (OData), utility APIs (Green Button / ESME), and Concur (REST API) that automatically ingest data without human intervention.

**Why we didn't build it:**

**SAP OData:** Requires SAP Gateway configuration and OAuth client registration on the client's SAP system. This is a multi-week IT engagement, not a prototype-scope task. The authorization model (which BAPIs the service account can call) varies by client.

**Utility APIs:** No standard. UK has ESME for smart meters; US has Green Button; Europe varies by country. Even where an API exists, programmatic access for enterprise accounts is often not enabled by default and requires a utility account manager.

**Concur API:** Well-documented REST API, but requires OAuth 2.0 enterprise app registration with SAP Concur, which takes days and requires client IT. The Expense Extract CSV export is what sustainability teams actually have access to today.

**What we did instead:** File upload with a parser that accepts the exact CSV format each platform already exports. The ingestion architecture (IngestionJob → parser → EmissionRecord) is designed so a pull integration would just replace the file upload step — the normalization pipeline is unchanged.

**Cost of this tradeoff:** Manual uploads. A client with weekly data will need to upload 3 CSV files per week. This is workable at onboarding scale; it doesn't scale to 50 clients.

---

## 3. Currency Normalization and Spend-Based Scope 3

**What it is:** Converting procurement spend to a common currency (USD/GBP) and applying spend-based emission factors (e.g., EXIOBASE multi-regional input-output model) to estimate Scope 3 Category 1 emissions from purchased goods.

**Why we didn't build it:**

**Currency normalization** requires: storing the exchange rate at the time of the transaction (not today's rate — a January purchase in EUR should use the January EUR/GBP rate), a source for historical rates (ECB API, Bloomberg, etc.), and logic to handle invoices that span multiple currencies in one SAP export.

**Spend-based Scope 3** is technically and methodologically complex. EXIOBASE provides kg CO2e per £1 of spend by sector, but SAP material groups don't map cleanly to EXIOBASE sectors. A proper mapping requires either: (a) client-specific spend mapping exercises (weeks of consultant time) or (b) an approximate sector mapping that introduces significant uncertainty that must be disclosed.

For Scope 3 Category 1, the GHG Protocol explicitly allows spend-based approximations, but requires disclosing the methodology and uncertainty. A prototype that shows CO2e numbers for purchased goods without this disclosure would be misleading.

**What we did instead:** SAP procurement rows that aren't fuel are classified as Scope 3 Category 1, `co2e_kg` is left null, and the record is flagged for manual factor assignment. The data model supports adding the factor later (multiply `quantity` by the factor and store in `co2e_kg`).

**Cost of this tradeoff:** Incomplete Scope 3 Category 1 coverage. For a client whose Scope 3 is dominated by purchased goods (e.g., a manufacturing company), this is a significant gap. For a services firm whose Scope 3 is mainly business travel, the impact is smaller.
