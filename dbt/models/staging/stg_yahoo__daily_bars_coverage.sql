with source as (
    select * from {{ source('raw', 'raw_yahoo_equity_daily_bars_coverage') }}
),

renamed as (
    select
        cast(yahoo_ticker as string) as yahoo_ticker,
        cast(status as string) as status,
        cast(row_count as int64) as row_count,
        cast(start_date as date) as start_date,
        cast(end_date as date) as end_date,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by start_date, end_date, yahoo_ticker
    order by _ingested_at desc
) = 1
