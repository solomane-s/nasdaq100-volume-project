{{ config(materialized='table') }}

select
    d.date_day as date_key,
    coalesce(v.volume, 0) as volume
from {{ ref('dim_date') }} d
left join {{ ref('stg_nasdaq_volume') }} v
    on d.date_day = v.trading_date
where d.date_day <= current_date()