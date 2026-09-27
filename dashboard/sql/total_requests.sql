SELECT count(*) AS total_requests
FROM dev_marts.fct_requests
WHERE true
[[AND {{request_date}}]]
[[AND {{borough}}]]
