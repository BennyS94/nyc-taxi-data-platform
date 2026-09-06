select
    *,
    pickup_datetime::date as pickup_date,
    dropoff_datetime::date as dropoff_date,
    extract(epoch from (dropoff_datetime - pickup_datetime)) as trip_duration_seconds
from {{ ref('int_trips_normalized') }}
