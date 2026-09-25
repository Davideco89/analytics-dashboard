# Dashboard user guide

## Purpose and views

The **NYC 311 Service Requests** dashboard shows the volume, mix, timing, and closing duration of service requests in the configured data window.

| View | Interpretation |
| --- | --- |
| Total Requests | Number of request rows after dashboard filters; one row per request. |
| Average Resolution Days | Average `resolution_hours / 24` for requests closed with a nonnegative closing interval; requests without a valid interval are excluded. |
| Complaint Volume Over Time | Request counts grouped by request date. |
| Top Complaint Types by Borough | Complaint counts by category and borough. |
| Complaint Heatmap by Time of Day | Request counts by day of week and hour of creation; the colored table represents volume. |

## Filters

- **Request Date** selects the creation date (`request_date` in the fact model), not the closing date. A one-day selection should affect the request count, time series, and time-of-day view consistently.
- **Borough** limits requests by the value reported in the source. `UNSPECIFIED` indicates an unknown or unassigned borough and should not be treated as a sixth NYC borough.

The dataset contains requests created from August 1 through August 7, 2026. A missing closing timestamp, an `OPEN` status, or a closing timestamp earlier than creation does not contribute to Average Resolution Days. The complaint type is the source category, not a standardized taxonomy across agencies. Coordinate and borough quality flags are available in the fact model but are not automatically applied as global dashboard filters.

## Reproducibility and access

The dashboard was configured in a local Metabase instance. Saved questions, native SQL, filter connections, users, and subscriptions are stored in the Metabase application volume rather than this repository. A fresh clone builds the analytical tables but requires the dashboard to be recreated or its metadata to be imported after a suitable export is added. User-level permissions, subscriptions, and an export of dashboard definitions remain to be documented and verified on the local instance.
