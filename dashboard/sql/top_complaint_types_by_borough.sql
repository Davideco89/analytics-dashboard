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
