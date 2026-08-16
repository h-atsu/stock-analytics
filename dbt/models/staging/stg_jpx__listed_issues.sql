with source as (
    select * from {{ source('raw', 'raw_jpx_listed_issues') }}
),

renamed as (
    select
        cast(snapshot_date as date) as snapshot_date,
        cast(security_code as string) as security_code,
        cast(security_name as string) as security_name,
        cast(market_product_category as string) as market_product_category,
        cast(sector_33_code as string) as sector_33_code,
        cast(sector_33_name as string) as sector_33_name,
        cast(sector_17_code as string) as sector_17_code,
        cast(sector_17_name as string) as sector_17_name,
        cast(scale_code as string) as scale_code,
        cast(scale_category as string) as scale_category,
        cast(yahoo_ticker as string) as yahoo_ticker,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by snapshot_date, security_code
    order by _ingested_at desc
) = 1
