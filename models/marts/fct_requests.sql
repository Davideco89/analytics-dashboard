with requests as (

    select *
    from {{ ref('stg_nyc_311') }}

),

enriched as (

    select
        request_id,
        md5(complaint_type) as complaint_type_key,

        created_at,
        closed_at,
        cast(created_at as date) as request_date,
        cast(date_trunc('week', created_at) as date) as request_week,
        extract(hour from created_at) as request_hour,
        dayname(created_at) as request_day_name,

        agency,
        agency_name,
        descriptor,
        location_type,
        incident_zip,
        city,
        status,
        due_at,
        resolution_description,
        resolution_updated_at,

        borough,
        community_board,
        council_district,
        open_data_channel,
        latitude,
        longitude,

        status = 'CLOSED' as is_closed,

        (
            status = 'CLOSED'
            and closed_at is not null
            and closed_at >= created_at
        ) as has_valid_resolution,

        case
            when status = 'CLOSED'
             and closed_at is not null
             and closed_at >= created_at
            then date_diff('second', created_at, closed_at) / 3600.0
        end as resolution_hours,

        (
            borough is not null
            and borough <> 'UNSPECIFIED'
        ) as has_valid_borough,

        (
            latitude is not null
            and longitude is not null
        ) as has_valid_coordinates,

        1 as request_count,

        loaded_at,
        source_file

    from requests

)

select *
from enriched