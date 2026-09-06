{{ config(materialized='table') }}

select
    cast(0 as integer) as vendor_key,
    cast(null as integer) as vendor_id,
    cast('Unknown' as text) as vendor_name

union all

select
    vendor_id as vendor_key,
    vendor_id,
    vendor_name
from {{ ref('tlc_vendors') }}
