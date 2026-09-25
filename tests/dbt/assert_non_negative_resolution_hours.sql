select
    request_id,
    resolution_hours
from {{ ref('fct_requests') }}
where resolution_hours < 0