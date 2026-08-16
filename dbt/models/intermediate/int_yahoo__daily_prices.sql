with yahoo as (
    select
        trade_date,
        concat(security_code, '0') as security_code,
        yahoo_ticker,
        open,
        high,
        low,
        close,
        volume,
        open as split_adjusted_open,
        high as split_adjusted_high,
        low as split_adjusted_low,
        close as split_adjusted_close,
        volume as split_adjusted_volume,
        dividends as dividend_per_share,
        stock_splits as stock_split_ratio,
        capital_gains,
        adjusted_close as yahoo_adjusted_close
    from {{ ref('stg_yahoo__daily_bars') }}
)

select * from yahoo
