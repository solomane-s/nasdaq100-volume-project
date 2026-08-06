with source as (
    select * from {{ source('raw', 'RAW_NASDAQ_VOLUME') }}
),

cleaned as (
    select
        try_to_date(date) as trading_date,
        volume
    from source
    where volume is not null
)

select * from cleaned