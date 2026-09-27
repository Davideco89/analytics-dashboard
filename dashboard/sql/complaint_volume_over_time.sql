SELECT request_date, count(*) AS requests
FROM dev_marts.fct_requests
WHERE true
[[AND {{request_date}}]]
[[AND {{borough}}]]
GROUP BY request_date
ORDER BY request_date
