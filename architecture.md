# ChargeCast — Architecture Specification, February 2026

Here is the architecture specification for the ChargeCast Django + Supabase + React + Tailwind app. 

The architectural approach was produced from this ChatGPT conversation on Tuesday 17th February 2026: https://chatgpt.com/share/6995ce7b-f574-8003-85c3-1639a9d10503.

---

## 1️⃣ System Overview

### Project Positioning

ChargeCast is a **climate-aware fleet optimisation engine** that:

* Ingests national and regional carbon intensity forecasts from the NESO Carbon Intensity API: https://carbon-intensity.github.io/api-definitions/#carbon-intensity-api-v2-0-0
* Persists interval-based carbon intensity records
* Maps UK postcodes to DNO regions
* Calculates fleet charging emissions from uploaded CSV files
* Computes optimisation metrics (avoidable emissions, charging quality, etc.)
* Provides dashboard visualisations and map-based charging insights

---

### Core Architectural Principles

* Smart API (aggregation and logic in backend)
* Immutable fleet charging ledger
* Interval-containment carbon lookup
* Region snapshot storage (region_id + region_shortname)
* 30-minute forecast ingestion via scheduled job
* Normalised carbon intensity interval storage
* Standardised API response envelope
* Structured logging
* Graceful fallback hierarchy
* Supabase Postgres as primary data store
* Django REST backend
* React + Tailwind + Recharts frontend
* React Leaflet for spatial visualisation

---

### System Pillars

1. Carbon Data Platform

   * Forecast ingestion
   * National forecast + actual
   * Regional forecast
   * Forecast error analytics

2. Operational Optimisation Dashboard

   * 48-hour forecast
   * Optimal charging windows
   * Charger map (137-mile radius)

3. Fleet Emissions Engine

   * CSV ingestion
   * Immutable charging ledger
   * Emissions computation
   * Avoidable emissions analysis

---

## 2️⃣ Carbon Lookup Logic

### Purpose

Given:

* postcode
* charged_at timestamp

Determine:

* region
* correct carbon intensity interval
* fallback if necessary

---

### Step 1 — Normalize Input

* Uppercase + strip postcode
* Ensure charged_at is timezone-aware UTC

---

### Step 2 — Resolve Postcode → Region

1. Check PostcodeRegionCache table
2. If missing → call NESO regional postcode endpoint
3. Cache:

   * postcode
   * region_id
   * region_shortname
   * resolved_at

Cache refresh policy: 90 days

---

### Step 3 — Interval Containment Query

Primary lookup:

Find CarbonIntensityRecord where:

* region_id = resolved_region
* valid_from <= charged_at < valid_to
* is_national = false

Use:

* forecast
* intensity_type_used = "regional_forecast"

---

## 3️⃣ Fallback Hierarchy

If regional interval not found:

Fallback A:

* National record
* valid_from <= charged_at < valid_to
* actual IS NOT NULL
* intensity_type_used = "national_actual"

Fallback B:

* National record
* valid_from <= charged_at < valid_to
* intensity_type_used = "national_forecast"

If still missing:

* Mark row failed
* Log structured error

---

## 4️⃣ Fleet Schema

### FleetUploadBatch

* id
* filename
* uploaded_at
* rows_received
* rows_processed
* rows_failed
* fallback_rows
* total_kwh
* total_emissions_kg
* processing_status
* error_message (nullable)

---

### FleetChargingEvent (Immutable Ledger)

* id
* batch (FK)
* vehicle_id
* postcode
* charged_at (UTC)
* region_id
* region_shortname
* kwh_consumed
* carbon_intensity_used (gCO₂/kWh)
* intensity_type_used

  * regional_forecast
  * national_actual
  * national_forecast
* calculated_emissions_kg
* created_at

Indexes:

* (vehicle_id, charged_at)
* (region_id, charged_at)
* (postcode)

Immutable by design — no update endpoint.

---

## 5️⃣ API Response Envelope

All endpoints return:

```json
{
  "status": "success" | "warning" | "error",
  "data": { ... },
  "meta": {
    "generated_at": "ISO8601",
    "source": "db" | "live" | "fallback",
    "message": "optional"
  }
}
```

Examples:

Success:

* status = "success"

Fallback:

* status = "warning"
* meta.message = "Using last known forecast due to upstream API issue."

Error:

* status = "error"
* data may be null
* meta.message explains error

---

## 6️⃣ Avoidable Emissions Formula

### For each charging event:

Define:

optimal_intensity = minimum forecast intensity within next 48 hours for same region

avoidable_kg =
max(0, (carbon_intensity_used - optimal_intensity) * kwh_consumed / 1000)

---

### Fleet-Level Metrics

Total avoidable emissions:
SUM(avoidable_kg)

Avoidable emissions percentage:
SUM(avoidable_kg) / SUM(calculated_emissions_kg)

---

### Additional Fleet Metrics

Total kWh:
SUM(kwh_consumed)

Total emissions:
SUM(calculated_emissions_kg)

Weighted average intensity:
1000 * SUM(calculated_emissions_kg) / SUM(kwh_consumed)

Green charging share (kWh-weighted):
SUM(kwh where intensity < green_threshold) / SUM(kwh)

---

## 7️⃣ Charger & Tariff Data Architecture (Phase 3A)

### Purpose

ChargeCast’s operational dashboard includes a charger map and charger-level insights. To support this, the backend needs a charger + tariff data platform that is:

* Multi-provider
* Idempotent (safe to re-run)
* Operationally observable (freshness, provenance, and staleness)
* Resilient to partial upstream failures

---

### Charger + Tariff Data Model (OCPI-Aligned)

Persist an OCPI-like hierarchy:

* ChargerLocation
* EVSE (per location)
* Connector (per EVSE)
* Tariff (separate entity)
* ConnectorTariff join table (FK to Tariff, not a string tariff_id)

Operational safety fields (critical for ingestion systems):

* source_provider (where the record came from)
* ingested_at (explicitly updated on every ingestion run)
* is_active (soft-delete for locations missing from a feed)
* last_seen_at / is_stale (tariffs only)

---

### Provider Strategy

Provider integrations fall into three buckets:

1. Aggregator API (Eco-Movement PCPR)

   * One shared OCPI surface
   * Multiple providers (Blink, BP Pulse, Ionity, Shell)
   * Provider-specific API keys

2. Individual OCPI provider (Fastned)

   * OCPI endpoints
   * API-key authentication
   * Standalone reliability profile (must be isolated from aggregator failures)

3. Non-OCPI provider (Motor Fuel Group)

   * Non-OCPI envelope and data shape
   * Public endpoints (no auth)
   * Requires extra defensive parsing + rate-limit protection

Char.gy is treated as locations-only (no tariff endpoint), even though it can emit tariff_ids.

---

### Separation of Concerns: Location vs Tariff Ingestion

Charging locations and tariffs evolve on different cadences and have different failure modes.

* Location ingestion owns:
  * ChargerLocation / EVSE / Connector upserts
  * Soft-delete (is_active false when locations disappear)
  * Connector → Tariff ID linkage via ConnectorTariff (only when the Tariff exists)

* Tariff ingestion owns:
  * Tariff upserts and explicit freshness tracking (ingested_at, last_seen_at)
  * Handling unreferenced tariffs (store them even if no connector references exist)
  * Staleness marking is NOT performed here

---

### Canonical Map Output: Pricing + Availability

The frontend should not need provider-specific logic to render charger pricing and availability.

ChargeCast will expose canonical outputs:

* cheapest_price (cheapest connector quote, regardless of operational status)
* cheapest_available_now (cheapest operationally usable connector quote)

Operationally usable is defined as:

* INCLUDE: AVAILABLE, UNKNOWN
* EXCLUDE: OUT_OF_ORDER (and other explicitly non-operational statuses)

When a connector/EVSE status is UNKNOWN:

* Treat as usable, but mark availability confidence as LOW
* Allow the UI to show an amber caution indicator (status uncertain)

Pricing estimates will return:

* a canonical TariffQuote-like output (total cost, breakdown, currency)
* a confidence level and explicit assumptions when tariff data is incomplete

---

### Stale Tariff Detection

Stale tariffs are expected in real-world provider feeds.

A dedicated stale detection job:

* marks Tariff.is_stale = true when last_seen_at is older than threshold (default 7 days)
* can unmark stale when a tariff is seen again
* provides operational metrics (counts marked/unmarked)

This is implemented as a separate service + management command to keep ingestion write paths simple.

---

### Scheduling (Render Cron)

To keep the platform current while controlling cost:

* Location ingestion — hourly (high freshness requirement)
* Tariff ingestion — daily (tariffs change less frequently)
* Stale detection — daily (after tariff ingestion)

Each job is independently runnable via management command, enabling:

* local testing
* ad-hoc re-ingestion for debugging
* clean operational observability in production logs

---

## 8️⃣ Roadmap Phases

### Phase 1 — Data Models & Migrations

* CarbonIntensityRecord
* PostcodeRegionCache
* ChargerLocation
* Region (optional)
* FleetUploadBatch
* FleetChargingEvent

---

### Phase 2 — Carbon Ingestion

* National + regional forecast ingestion
* 30-minute scheduled job (Render cron)
* Normalised interval storage
* Structured logging

---

### Phase 3A — Charger Data and Tariff Foundations

* Charger, EVSE, Connector, Tariff, ConnectorTariff models (OCPI-aligned)
* Provider API clients (Eco-Movement, Fastned, Char.gy, MFG)
* Multi-provider location ingestion orchestration (idempotent + soft-delete)
* Separate tariff ingestion orchestration (explicit last_seen_at + ingested_at tracking)
* Stale tariff detection service + management command
* Render cron scheduling (hourly locations, daily tariffs, daily stale detection)
* Comprehensive ingestion test suite with fixture provider responses
* Canonical charger map pricing/availability outputs (cheapest vs available-now + confidence)

---

### Phase 3B — Fleet Upload Engine

* CSV schema definition & validation
* Postcode resolution service (postcode → GSP)
* Carbon intensity lookup service (local cache first, NESO fallback)
* Django-RQ background task orchestration for uploads
* CSV parser + row processing (postcode + carbon enrichment)
* Upload API endpoint (multipart/form-data + validation + rate limits)
* Batch status API endpoint
* Batch summary + metrics calculation endpoint
* Comprehensive upload engine test suite with fixture CSVs

---

### Phase 4 — Fleet Analytics API

* Fleet summary endpoint
* Timeseries endpoint
* Region breakdown
* Vehicle breakdown
* Avoidable emissions endpoint

---

### Phase 5 — Frontend Integration

* CSV upload UI
* Batch result screen
* Fleet dashboard
* Forecast visualisation
* Map with 137-mile radius charger filtering

---

### Phase 6 — Testing & Deployment

* Model tests
* Ingestion tests
* Fleet upload tests
* Deploy backend to Render
* Deploy frontend to Vercel
* Configure Supabase

---