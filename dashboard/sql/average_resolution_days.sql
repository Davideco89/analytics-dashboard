SELECT round(avg(resolution_hours) / 24.0, 2) AS avg_resolution_days
FROM dev_marts.fct_requests
WHERE has_valid_resolution
[[AND {{request_date}}]]
[[AND {{borough}}]]
