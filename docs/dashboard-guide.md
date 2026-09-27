# Dashboard user guide

## Recreate the dashboard

After running `python scripts/update_data.py`, connect Metabase to the DuckDB file at `/home/metabase/data/analytics.duckdb`. Create five **New → SQL query** questions against **NYC 311 Analytics**, using the SQL below or the corresponding versioned `.sql` files in [`dashboard/sql/`](../dashboard/sql/). Save each under its heading and add it to a dashboard named **NYC 311 Service Requests**. The queries work without filter values. The repository tests check that the copies in this guide match the `.sql` files.

Every question contains `{{request_date}}` and `{{borough}}`. In its variable sidebar, set each variable type to **Field Filter**, map `request_date` to **dev_marts → fct_requests → request_date** (date picker) and `borough` to **dev_marts → fct_requests → borough** (dropdown). Leave both optional and with no default value. The fact table is deliberately unaliased in every query, including the one with a dimension join, so Metabase needs no table/field alias override. Do not add a column or an equals sign inside `{{...}}`.

In dashboard edit mode, add a **Request Date** date filter and a **Borough** text/category filter. On **each of the five cards**, map the first dashboard filter to that card's `request_date` parameter and the second to its `borough` parameter, then save. Clear both to see the full current window; selecting one date or one borough should consistently change all five questions. The Request Date filter applies to the *creation* date, not the closure date.

## Total Requests

Choose the **Number** visualization. Each fact row represents exactly one request.

SQL file: [`dashboard/sql/total_requests.sql`](../dashboard/sql/total_requests.sql).

```sql
SELECT count(*) AS total_requests
FROM dev_marts.fct_requests
WHERE true
[[AND {{request_date}}]]
[[AND {{borough}}]]
```

## Average Resolution Days

Choose the **Number** visualization and display two decimals. Only closed requests with a nonnegative closing interval contribute; other requests remain in the total card.

SQL file: [`dashboard/sql/average_resolution_days.sql`](../dashboard/sql/average_resolution_days.sql).

```sql
SELECT round(avg(resolution_hours) / 24.0, 2) AS avg_resolution_days
FROM dev_marts.fct_requests
WHERE has_valid_resolution
[[AND {{request_date}}]]
[[AND {{borough}}]]
```

## Complaint Volume Over Time

Choose a **Line** visualization with `request_date` as the horizontal axis and `requests` as the vertical axis.

SQL file: [`dashboard/sql/complaint_volume_over_time.sql`](../dashboard/sql/complaint_volume_over_time.sql).

```sql
SELECT request_date, count(*) AS requests
FROM dev_marts.fct_requests
WHERE true
[[AND {{request_date}}]]
[[AND {{borough}}]]
GROUP BY request_date
ORDER BY request_date
```

## Top Complaint Types by Borough

Choose a **Bar** visualization: complaint type on the horizontal axis, `requests` on the vertical axis, break out by borough, and stack bars. This selects the ten most frequent complaint types **after** applying the date and borough filters, then breaks those categories into the five recognized boroughs. The join resolves `complaint_type_key` to the display name; unknown boroughs do not enter this card.

SQL file: [`dashboard/sql/top_complaint_types_by_borough.sql`](../dashboard/sql/top_complaint_types_by_borough.sql).

```sql
WITH filtered_requests AS (
    SELECT complaint_type_key, borough
    FROM dev_marts.fct_requests
    WHERE has_valid_borough
    [[AND {{request_date}}]]
    [[AND {{borough}}]]
),
top_types AS (
    SELECT complaint_type_key, count(*) AS total_requests
    FROM filtered_requests
    GROUP BY complaint_type_key
    ORDER BY count(*) DESC, complaint_type_key
    LIMIT 10
)
SELECT dev_marts.dim_complaint_type.complaint_type,
       filtered_requests.borough,
       count(*) AS requests
FROM filtered_requests
JOIN top_types
    ON filtered_requests.complaint_type_key = top_types.complaint_type_key
JOIN dev_marts.dim_complaint_type
    ON filtered_requests.complaint_type_key =
       dev_marts.dim_complaint_type.complaint_type_key
GROUP BY dev_marts.dim_complaint_type.complaint_type,
         filtered_requests.borough, top_types.total_requests
ORDER BY top_types.total_requests DESC,
         dev_marts.dim_complaint_type.complaint_type, filtered_requests.borough
```

## Complaint Heatmap by Time of Day

Choose a **Table** visualization. Apply conditional formatting as a color range to the 24 hour columns. The SQL creates the seven weekday rows and 24 hour columns directly; Metabase does not support its Pivot Table visualization for native SQL questions.

SQL file: [`dashboard/sql/complaint_heatmap_by_time_of_day.sql`](../dashboard/sql/complaint_heatmap_by_time_of_day.sql).

```sql
SELECT request_day_name,
       count(*) FILTER (WHERE request_hour = 0) AS "00",
       count(*) FILTER (WHERE request_hour = 1) AS "01",
       count(*) FILTER (WHERE request_hour = 2) AS "02",
       count(*) FILTER (WHERE request_hour = 3) AS "03",
       count(*) FILTER (WHERE request_hour = 4) AS "04",
       count(*) FILTER (WHERE request_hour = 5) AS "05",
       count(*) FILTER (WHERE request_hour = 6) AS "06",
       count(*) FILTER (WHERE request_hour = 7) AS "07",
       count(*) FILTER (WHERE request_hour = 8) AS "08",
       count(*) FILTER (WHERE request_hour = 9) AS "09",
       count(*) FILTER (WHERE request_hour = 10) AS "10",
       count(*) FILTER (WHERE request_hour = 11) AS "11",
       count(*) FILTER (WHERE request_hour = 12) AS "12",
       count(*) FILTER (WHERE request_hour = 13) AS "13",
       count(*) FILTER (WHERE request_hour = 14) AS "14",
       count(*) FILTER (WHERE request_hour = 15) AS "15",
       count(*) FILTER (WHERE request_hour = 16) AS "16",
       count(*) FILTER (WHERE request_hour = 17) AS "17",
       count(*) FILTER (WHERE request_hour = 18) AS "18",
       count(*) FILTER (WHERE request_hour = 19) AS "19",
       count(*) FILTER (WHERE request_hour = 20) AS "20",
       count(*) FILTER (WHERE request_hour = 21) AS "21",
       count(*) FILTER (WHERE request_hour = 22) AS "22",
       count(*) FILTER (WHERE request_hour = 23) AS "23"
FROM dev_marts.fct_requests
WHERE true
[[AND {{request_date}}]]
[[AND {{borough}}]]
GROUP BY request_day_name
ORDER BY CASE request_day_name
    WHEN 'Monday' THEN 1
    WHEN 'Tuesday' THEN 2
    WHEN 'Wednesday' THEN 3
    WHEN 'Thursday' THEN 4
    WHEN 'Friday' THEN 5
    WHEN 'Saturday' THEN 6
    WHEN 'Sunday' THEN 7
END
```

## Interpretation and checks

The source complaint type is not a taxonomy shared by all agencies. `UNSPECIFIED` indicates an unknown or unassigned borough, not a sixth borough; only the top complaint card excludes it by design. Missing/invalid closing timestamps are excluded only from the resolution average. Coordinate quality flags exist in the fact model but are not global filters.

The screenshot in `dashboard/screenshots/` records an August 1–7, 2026 historical run; a fresh rolling run covers seven New York calendar days with a one-day source-delivery buffer. A refresh on September 27 selects September 19–25, avoiding the source's partial September 26 records. Check the extraction log for its exact `[start, end)` window.

Metabase Open Source stores saved cards, dashboard layout and filter connections in its separate local application volume. A fresh clone does not import that state; the SQL and configuration above recreate the five views without access to the original volume. Do not remove the application volume if you want to preserve your saved dashboard.
