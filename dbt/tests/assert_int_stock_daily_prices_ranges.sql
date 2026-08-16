select *
from {{ ref('int_stock__daily_prices') }}
where
    (high is not null and low is not null and high < low)
    or (
        split_adjusted_high is not null
        and split_adjusted_low is not null
        and split_adjusted_high < split_adjusted_low
    )
