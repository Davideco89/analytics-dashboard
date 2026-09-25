select distinct
    md5(complaint_type) as complaint_type_key,
    complaint_type
from {{ ref('stg_nyc_311') }}