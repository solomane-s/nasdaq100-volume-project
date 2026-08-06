select
    date_key,
    volume,
    avg(volume) over (order by date_key rows between 6 preceding and current row) as volume_7d_avg
from {{ ref('fact_daily_volume') }}
order by date_key