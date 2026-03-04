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

## 7️⃣ Roadmap Phases

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

### Phase 3 — Fleet Upload Engine

* CSV validation
* Lenient row handling
* Bulk insert
* Fallback tracking
* Batch summary

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
