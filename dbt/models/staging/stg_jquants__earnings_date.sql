with source as (
    select * from {{ source('raw', 'raw_jquants_earnings_date') }}
),

renamed as (
    select
        cast(PubDate as date) as publication_date,
        date(timestamp_micros(div(SchDate, 1000))) as scheduled_date,
        cast(FQName as string) as fiscal_quarter_name,
        cast(FYE as string) as fiscal_year_end,
        cast(Code as string) as security_code,
        cast(CoName as string) as company_name,
        cast(CoNameEn as string) as company_name_en,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by publication_date, security_code, fiscal_quarter_name
    order by _ingested_at desc
) = 1
