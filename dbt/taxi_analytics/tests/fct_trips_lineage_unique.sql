select
    source_file_id,
    source_row_number
from {{ ref('fct_trips') }}
group by 1, 2
having count(*) > 1
