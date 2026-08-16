with source as (
    select * from {{ source('raw', 'raw_jquants_financial_summary') }}
),

renamed as (
    select
        cast(DiscDate as date) as disclosure_date,
        cast(DiscTime as string) as disclosure_time,
        cast(Code as string) as security_code,
        cast(DiscNo as string) as disclosure_number,
        cast(DocType as string) as document_type,
        cast(CurPerType as string) as current_period_type,
        date(timestamp_micros(div(CurPerSt, 1000))) as current_period_start_date,
        date(timestamp_micros(div(CurPerEn, 1000))) as current_period_end_date,
        date(timestamp_micros(div(CurFYSt, 1000))) as current_fiscal_year_start_date,
        date(timestamp_micros(div(CurFYEn, 1000))) as current_fiscal_year_end_date,
        date(timestamp_micros(div(NxtFYSt, 1000))) as next_fiscal_year_start_date,
        date(timestamp_micros(div(NxtFYEn, 1000))) as next_fiscal_year_end_date,
        safe_cast(Sales as numeric) as sales,
        safe_cast(OP as numeric) as operating_profit,
        safe_cast(OdP as numeric) as ordinary_profit,
        safe_cast(NP as numeric) as net_profit,
        safe_cast(EPS as numeric) as earnings_per_share,
        safe_cast(DEPS as numeric) as diluted_earnings_per_share,
        safe_cast(TA as numeric) as total_assets,
        safe_cast(Eq as numeric) as equity,
        safe_cast(EqAR as numeric) as equity_to_asset_ratio,
        safe_cast(BPS as numeric) as book_value_per_share,
        safe_cast(CFO as numeric) as cash_flow_from_operations,
        safe_cast(CFI as numeric) as cash_flow_from_investing,
        safe_cast(CFF as numeric) as cash_flow_from_financing,
        safe_cast(CashEq as numeric) as cash_and_equivalents,
        safe_cast(DivAnn as numeric) as annual_dividend_per_share,
        safe_cast(FDivAnn as numeric) as forecast_annual_dividend_per_share,
        safe_cast(NxFDivAnn as numeric) as next_forecast_annual_dividend_per_share,
        safe_cast(FSales as numeric) as forecast_sales,
        safe_cast(FOP as numeric) as forecast_operating_profit,
        safe_cast(FOdP as numeric) as forecast_ordinary_profit,
        safe_cast(FNP as numeric) as forecast_net_profit,
        safe_cast(FEPS as numeric) as forecast_earnings_per_share,
        safe_cast(NxFSales as numeric) as next_forecast_sales,
        safe_cast(NxFOP as numeric) as next_forecast_operating_profit,
        safe_cast(NxFOdP as numeric) as next_forecast_ordinary_profit,
        safe_cast(NxFNp as numeric) as next_forecast_net_profit,
        safe_cast(NxFEPS as numeric) as next_forecast_earnings_per_share,
        safe_cast(ShOutFY as numeric) as shares_outstanding,
        safe_cast(TrShFY as numeric) as treasury_shares,
        safe_cast(AvgSh as numeric) as average_shares,
        safe_cast(ROE as numeric) as return_on_equity,
        cast(MatChgSub as string) as material_subsidiary_change_flag,
        cast(SigChgInC as string) as significant_change_in_scope_flag,
        cast(ChgByASRev as string) as accounting_standard_revision_flag,
        cast(ChgNoASRev as string) as accounting_policy_change_flag,
        cast(ChgAcEst as string) as accounting_estimate_change_flag,
        cast(RetroRst as string) as retrospective_restatement_flag,
        cast(_ingested_at as timestamp) as _ingested_at,
        cast(_source as string) as _source
    from source
)

select * from renamed
qualify row_number() over (
    partition by disclosure_date, security_code, disclosure_number
    order by _ingested_at desc
) = 1
