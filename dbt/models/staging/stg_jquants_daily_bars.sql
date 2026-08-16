with source as (
    select * from {{ source('raw', 'raw_jquants_equity_daily_bars') }}
),

renamed as (
    select
        cast(Date as date) as trade_date,
        cast(Code as string) as security_code,
        cast(O as float64) as open,
        cast(H as float64) as high,
        cast(L as float64) as low,
        cast(C as float64) as close,
        cast(UL as string) as upper_limit_flag,
        cast(LL as string) as lower_limit_flag,
        cast(Vo as float64) as volume,
        cast(Va as float64) as turnover_value,
        cast(AdjFactor as float64) as adjustment_factor,
        cast(AdjO as float64) as adjusted_open,
        cast(AdjH as float64) as adjusted_high,
        cast(AdjL as float64) as adjusted_low,
        cast(AdjC as float64) as adjusted_close,
        cast(AdjVo as float64) as adjusted_volume,
        cast(MktCap as float64) as market_cap,
        cast(ExRT as string) as ex_rights_flag,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by trade_date, security_code
    order by _ingested_at desc
) = 1
