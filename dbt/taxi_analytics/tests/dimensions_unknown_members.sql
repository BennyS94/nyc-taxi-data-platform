select 'dim_zone' as dimension_name
where (
    select count(*)
    from {{ ref('dim_zone') }}
    where zone_key = 0
      and location_id is null
      and borough = 'Unknown'
      and zone_name = 'Unknown'
) <> 1

union all

select 'dim_vendor' as dimension_name
where (
    select count(*)
    from {{ ref('dim_vendor') }}
    where vendor_key = 0
      and vendor_id is null
      and vendor_name = 'Unknown'
) <> 1

union all

select 'dim_date' as dimension_name
where (
    select count(*)
    from {{ ref('dim_date') }}
    where date_key = 0
      and full_date is null
) <> 1
