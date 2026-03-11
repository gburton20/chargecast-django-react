# chargecast-django-react
ChargeCast is a climate-aware fleet optimisation engine with Django + Supabase + React + Tailwind. It is a refactored product based on a prior version jointly built by myself, George Burton, and my co-contributor, Blae Quayle, as part of the Software x Climate September 2025 cohort programme.

# Activating the venv for the backend/ folder

This repo standardises on a single Python virtual environment located at `backend/venv/`.

The venv folder should never be committed to GitHub (which is why it is included in .gitignore).

# To instantiate the venv for the first time from the repo root:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# To reactivate the venv during subsequent sessions:

```bash
cd backend
source venv/bin/activate
```

# Recommendation for Python interpreter choice

Ensure VS Code is using the backend virtual environment interpreter:

Python: Select Interpreter → `backend/venv/bin/python`

# Testing

Run the Django test suite for the `core`, `carbon` and `fleet` apps:

```bash
cd backend
python manage.py test app_1_name app_2_name app_3_name --keepdb --noinput
```

Notes:
- `--keepdb` avoids dropping/recreating the test database (useful with Supabase session pooler connections).
- `--noinput` prevents interactive prompts during the test run.

# Database setup and running migrations

This project's remote PostgreSQL databases are hosted via Supabase. 

There are three Django apps within this project: `core`, `carbon` and `fleet`. 

Here is a list of the names of DB models created per app:

1) `core`: Region, PostcodeRegionCache, ChargerLocation
2) `carbon`: CarbonIntensityRecord
3) `fleet`: FleetUploadBatch, FleetChargingEvent

Before running migrations, it is essential to configure the project's .env file with the correct env vars which are themselves derived from the project's Supabase connection settings:

1) DB_NAME
2) DB_USER
3) DB_PASSWORD
4) DB_HOST
5) DB_PORT

To generate migrations (only if models have been changed):

```bash
cd backend
python manage.py makemigrations
```

To apply migrations (recommended for new setups / pulling latest):

```bash
cd backend
python manage.py migrate
```

To confirm the status of your migrations:

```bash
cd backend
python manage.py showmigrations
```

# Orchestration of carbon data ingestion via CLI (for human input and Render cron jobs)

Use the management command below to orchestrate carbon ingestion jobs:

```bash
cd backend
python manage.py ingest_carbon_data [--national-only | --regional-only | --actual-only] [--dry-run]
```

Notes:
- If no `--*-only` flag is provided, all three jobs run (national forecast, regional forecast, national actual).
- The `--national-only`, `--regional-only`, and `--actual-only` flags are mutually exclusive (only one can be used per run).
- `--dry-run` executes the flow but rolls back database writes at the end.

Examples:

```bash
# Run all three ingestion jobs
cd backend
python manage.py ingest_carbon_data

# Run one job only
python manage.py ingest_carbon_data --national-only
python manage.py ingest_carbon_data --regional-only
python manage.py ingest_carbon_data --actual-only

# Dry-run variants (no persisted DB writes)
python manage.py ingest_carbon_data --dry-run
python manage.py ingest_carbon_data --national-only --dry-run
```

# Render cron job configuration for 30-minute ingestion

The Render cron job `chargecast-ingest-carbon-data-30m` runs `python manage.py ingest_carbon_data` every 30 minutes using the schedule `*/30 * * * *`. 

Its infrastructure is defined in `render.yaml`, with backend configured as the root directory and pip install -r requirements.txt as the build command. 

The job writes forecast and actual carbon intensity data to the `carbon_carbonintensityrecord` table in the project PostgreSQL database. 

The cron job must be configured with the same required environment variable values as the backend web service. It currently auto-deploys from the `dev` branch; production should point to `main`.

# Structured logging for carbon ingestion

The ingestion pipeline now uses structured JSON logs for:

- NESO API client requests, responses, retries, and errors
- Ingestion service lifecycle events (start, parse errors, DB errors, completion)
- Management command orchestration and final run summary

All logs are emitted to stdout via Django logging config (`backend/config/settings.py`) and are captured by Render automatically.

## Log schema

Each log entry includes:

- `timestamp`
- `level`
- `logger`
- `message`
- `event` (stable machine-readable event name)
- contextual fields (for example `run_id`, `scope`, `endpoint`, `status_code`, `records_created`, `records_failed`)

## Configuration

Environment variable:

- `LOG_LEVEL` (default: `INFO`)

Implementation files:

- `backend/config/logging.py` for JSON formatting
- `backend/config/settings.py` for logger/handler wiring

## Manual verification

Run the command locally:

```bash
cd backend
python manage.py ingest_carbon_data
```

Look for JSON log lines containing events such as:

- `ingestion_command_started`
- `neso_api_request_started`
- `ingestion_database_error`
- `ingestion_completed`
- `ingestion_command_completed`

For production verification, open Render logs for `chargecast-ingest-carbon-data-30m` and confirm the same events appear with metrics fields (`records_created`, `records_updated`, `records_skipped`, `records_failed`).