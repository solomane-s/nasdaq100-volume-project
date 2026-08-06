{{ config(materialized='table') }}

with date_spine as (
    select
        dateadd(day, seq4(), '2010-01-01') as date_day
    from table(generator(rowcount => 10000))
    where date_day <= current_date()
)

select
    date_day,
    year(date_day) as year,
    month(date_day) as month,
    monthname(date_day) as month_name,
    day(date_day) as day_of_month,
    dayofweek(date_day) as day_of_week,
    dayname(date_day) as day_name,
    quarter(date_day) as quarter,
    weekofyear(date_day) as week_of_year
from date_spine