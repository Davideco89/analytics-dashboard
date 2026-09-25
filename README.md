# NYC 311 Analytics Dashboard

An end-to-end local analytics project based on the [DataSkew DuckDB + Metabase project](https://dataskew.io/projects/analytics-dashboard/). Python extracts a fixed week of NYC 311 requests, Great Expectations validates the CSV, DuckDB stores the data, dbt builds analytical models, and Metabase displays the results. A scheduled GitHub Actions workflow runs the data pipeline in headless mode.

## Data and metrics

The source is the [NYC 311 Service Requests dataset](https://data.cityofnewyork.us/d/erm2-nwe9). The configured extraction covers `2026-08-01T00:00:00` through `2026-08-08T00:00:00` (exclusive), with pagination ordered by creation time and request key. Re-running the pipeline replaces this window's snapshot, including any source updates to existing requests; it does not append newer weeks. The latest verified snapshot had 73,771 requests and 154 complaint types. Counts and resolution times may change as the source updates.

| Object | Grain and purpose |
| --- | --- |
| `raw.nyc_311` | One source row per request; 20 selected API fields plus ingestion metadata. |
| `dev_staging.stg_nyc_311` | One typed, cleaned row per usable request; rows lacking a request ID, creation time, or complaint type are excluded. |
| `dev_marts.fct_requests` | One row per request with dates, geography flags, and resolution hours. |
| `dev_marts.dim_complaint_type` | One row per distinct complaint type. |

`request_count` is one per fact row. `has_valid_resolution` requires status `CLOSED`, a closing time, and `closed_at >= created_at`. `resolution_hours` is populated only for such requests. Average resolution days is `avg(resolution_hours) / 24` over valid resolutions; it is not an average across all requests. `has_valid_borough` recognizes the five NYC boroughs. `has_valid_coordinates` checks an approximate bounding rectangle (latitude 40.4–41.0, longitude −74.3–−73.6); it does not establish that a point lies inside city boundaries. Both geographic flags return false for missing values.

## Requirements

- Python **3.13** and Git. The tested Windows environment used Python 3.13.14. Python 3.14 is not the project baseline.
- Docker with Compose for the local Metabase dashboard.
- Network access to NYC Open Data for a full refresh.

Dependencies, including dbt core and its DuckDB adapter, are pinned in `requirements.txt`. The `.env` file and generated data remain local.

## Setup

Run commands from the repository root. On Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -s tests/python -v
docker compose build metabase
python scripts/update_data.py
docker compose up -d --wait metabase
```

On macOS or Linux with Python 3.13 available as `python3.13`:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m unittest discover -s tests/python -v
docker compose build metabase
python scripts/update_data.py
docker compose up -d --wait metabase
```

The macOS/Linux commands mirror the tested Windows workflow; execution on a macOS or Linux host has not yet been verified.

On a fresh setup, `update_data.py` can run before the Metabase container is created; Docker and Compose must still be available in the default `METABASE_MODE=auto`. The refresh downloads the data, runs seven raw-data expectations, loads a staging database, runs `dbt build`, backs up the previous analytical database if one exists, publishes the new database, and validates its row counts. If Metabase was running, the script stops it for the database swap and waits for it to become healthy again. A lock prevents two local refresh processes from running concurrently. The commands above use the default DuckDB path mounted by Compose; for a custom database path, review `METABASE_MODE` in `.env.example`.

Open [Metabase locally](http://localhost:3000) and add a DuckDB database pointing to `/home/metabase/data/analytics.duckdb`. The database directory is mounted read-only inside the container. Metabase stores its application configuration, users, saved questions, and dashboard in the local `metabase_state` Docker volume; the Compose port is bound to `127.0.0.1`.

For subsequent local refreshes, activate the virtual environment and run `python scripts/update_data.py`. The scheduled [GitHub Actions workflow](.github/workflows/update-data.yml) runs headlessly, tests and refreshes its own temporary database, and uploads the CSV, DuckDB file, and dbt results as artifacts. It does **not** update the DuckDB file or Metabase dashboard on your computer, and it does not test the live Metabase connection.

## Dashboard and project documentation

The local Metabase dashboard is **NYC 311 Service Requests**, with Total Requests, Average Resolution Days, Complaint Volume Over Time, Top Complaint Types by Borough, and Complaint Heatmap by Time of Day. Its Request Date and Borough filters were tested on the local instance. See the [dashboard guide](docs/dashboard-guide.md) for interpretation and usage, and the [architecture notes](docs/architecture.md) for refresh and backup behavior.

The saved Metabase questions and dashboard currently live only in the local application volume. Their SQL and metadata are not yet versioned here, so cloning this repository recreates the data platform but not the saved dashboard. Screenshots and dashboard export remain to be added before submission. No credentials or generated DuckDB files should be committed.

## DataSkew coverage

| Item | Status |
| --- | --- |
| DuckDB models, Metabase dashboard, date and borough filters | Implemented and locally verified |
| GitHub Actions refresh, logs, backup, local restart | Implemented; Actions validates the headless data pipeline |
| dbt-duckdb and Great Expectations extensions | Implemented |
| Dashboard SQL/metadata export, screenshots, user permissions, subscriptions or exports | Pending evidence or configuration |
| API refresh trigger, cloud Metabase deployment | Optional extensions not implemented |
