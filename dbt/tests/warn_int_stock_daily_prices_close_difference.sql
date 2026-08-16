{{ config(severity='warn') }}

select *
from {{ ref('int_stock__daily_prices') }}
where split_adjusted_close_relative_difference > 0.001
