with source as (
    select * from {{ source('raw', 'raw_yahoo_equity_daily_bars') }}
),

renamed as (
    select
        cast(trade_date as date) as trade_date,
        regexp_extract(cast(yahoo_ticker as string), r'^([0-9A-Z]{4})\.T$') as security_code,
        cast(yahoo_ticker as string) as yahoo_ticker,
        cast(open as float64) as open,
        cast(high as float64) as high,
        cast(low as float64) as low,
        cast(close as float64) as close,
        cast(adj_close as float64) as adjusted_close,
        cast(volume as float64) as volume,
        cast(dividends as float64) as dividends,
        cast(stock_splits as float64) as stock_splits,
        cast(capital_gains as float64) as capital_gains,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by trade_date, yahoo_ticker
    order by _ingested_at desc
) = 1
