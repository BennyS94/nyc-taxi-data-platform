select
    source_file_id,
    source_row_number
from {{ ref('int_trips_normalized') }}
group by 1, 2
having count(*) > 1
