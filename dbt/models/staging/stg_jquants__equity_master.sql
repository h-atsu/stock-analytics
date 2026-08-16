with source as (
    select * from {{ source('raw', 'raw_jquants_equity_master') }}
),

renamed as (
    select
        cast(Date as date) as snapshot_date,
        cast(Code as string) as security_code,
        cast(CoName as string) as company_name,
        cast(CoNameEn as string) as company_name_en,
        cast(S17 as string) as sector_17_code,
        cast(S17Nm as string) as sector_17_name,
        cast(S33 as string) as sector_33_code,
        cast(S33Nm as string) as sector_33_name,
        nullif(cast(ScaleCat as string), '-') as scale_category,
        cast(Mkt as string) as market_code,
        cast(MktNm as string) as market_name,
        cast(Mrgn as string) as margin_code,
        cast(MrgnNm as string) as margin_name,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by snapshot_date, security_code
    order by _ingested_at desc
) = 1
