with jquants as (
    select
        trade_date,
        security_code,
        open,
        high,
        low,
        close,
        volume,
        adjusted_open,
        adjusted_high,
        adjusted_low,
        adjusted_close,
        adjusted_volume
    from {{ ref('stg_jquants__daily_bars') }}
),

yahoo as (
    select
        trade_date,
        security_code,
        open,
        high,
        low,
        close,
        volume,
        split_adjusted_open,
        split_adjusted_high,
        split_adjusted_low,
        split_adjusted_close,
        split_adjusted_volume,
        dividend_per_share,
        stock_split_ratio,
        capital_gains
    from {{ ref('int_yahoo__daily_prices') }}
),

combined as (
    select
        coalesce(jquants.trade_date, yahoo.trade_date) as trade_date,
        coalesce(jquants.security_code, yahoo.security_code) as security_code,
        case when jquants.security_code is not null then jquants.open else yahoo.open end
            as open,
        case when jquants.security_code is not null then jquants.high else yahoo.high end
            as high,
        case when jquants.security_code is not null then jquants.low else yahoo.low end
            as low,
        case when jquants.security_code is not null then jquants.close else yahoo.close end
            as close,
        case
            when jquants.security_code is not null then jquants.volume
            else yahoo.volume
        end as volume,
        case
            when jquants.security_code is not null then jquants.adjusted_open
            else yahoo.split_adjusted_open
        end as split_adjusted_open,
        case
            when jquants.security_code is not null then jquants.adjusted_high
            else yahoo.split_adjusted_high
        end as split_adjusted_high,
        case
            when jquants.security_code is not null then jquants.adjusted_low
            else yahoo.split_adjusted_low
        end as split_adjusted_low,
        case
            when jquants.security_code is not null then jquants.adjusted_close
            else yahoo.split_adjusted_close
        end as split_adjusted_close,
        case
            when jquants.security_code is not null then jquants.adjusted_volume
            else yahoo.split_adjusted_volume
        end as split_adjusted_volume,
        yahoo.dividend_per_share,
        yahoo.stock_split_ratio,
        yahoo.capital_gains,
        case
            when jquants.security_code is not null then 'jquants'
            else 'yahoo'
        end as price_source,
        case when yahoo.security_code is not null then 'yahoo' end
            as corporate_action_source,
        jquants.security_code is null as is_provisional,
        jquants.security_code is not null as has_jquants,
        yahoo.security_code is not null as has_yahoo,
        jquants.close as jquants_close,
        yahoo.close as yahoo_close,
        jquants.adjusted_close as jquants_split_adjusted_close,
        yahoo.split_adjusted_close as yahoo_split_adjusted_close,
        safe_divide(
            abs(jquants.close - yahoo.close),
            abs(jquants.close)
        ) as close_relative_difference,
        safe_divide(
            abs(jquants.adjusted_close - yahoo.split_adjusted_close),
            abs(jquants.adjusted_close)
        ) as split_adjusted_close_relative_difference
    from jquants
    full outer join yahoo
        on
            jquants.trade_date = yahoo.trade_date
            and jquants.security_code = yahoo.security_code
)

select * from combined
