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
