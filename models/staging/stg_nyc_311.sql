with source as (

    select *
    from {{ source('raw', 'nyc_311') }}

),

cleaned as (

    select
        try_cast(unique_key as bigint) as request_id,
        try_cast(created_date as timestamp) as created_at,
        try_cast(closed_date as timestamp) as closed_at,

        nullif(trim(agency), '') as agency,
        nullif(trim(agency_name), '') as agency_name,
        nullif(trim(complaint_type), '') as complaint_type,
        nullif(trim(descriptor), '') as descriptor,
        nullif(trim(location_type), '') as location_type,

        nullif(trim(incident_zip), '') as incident_zip,
        upper(nullif(trim(city), '')) as city,
        upper(nullif(trim(status), '')) as status,

        try_cast(due_date as timestamp) as due_at,
        nullif(trim(resolution_description), '') as resolution_description,
        try_cast(
            resolution_action_updated_date as timestamp
        ) as resolution_updated_at,

        upper(nullif(trim(borough), '')) as borough,
        nullif(trim(community_board), '') as community_board,
        try_cast(council_district as integer) as council_district,
        upper(
            nullif(trim(open_data_channel_type), '')
        ) as open_data_channel,

        try_cast(latitude as double) as latitude,
        try_cast(longitude as double) as longitude,

        _loaded_at as loaded_at,
        _source_file as source_file

    from source

),

validated as (

    select *
    from cleaned
    where request_id is not null
      and created_at is not null
      and complaint_type is not null

)

select *
from validated