{% docs __overview__ %}

# stock-analytics

東証上場銘柄の価格・銘柄属性・財務・決算予定を、分析しやすい形へ整えるdbt projectです。

## データフロー

```text
J-Quants ─┐
Yahoo     ├─ raw_* ─ stg_* ─ int_* ─ mart_*
JPX      ─┤
seeds    ─┘
```

現在公開しているのはcanonical日次価格の`int_*`までです。`raw_*`は取得元の値と再取得履歴を保持し、コードマスターseedはJ-Quants同梱値を保持します。`stg_*`は列名と型を正規化し、`int_*`はYahooをJ-Quantsのコード・価格基準へ揃えてsourceを統合します。

## レイヤー責務

| prefix | 状態 | 責務 |
|---|---|---|
| `raw_` | 実装済み | 取得元別の値とingestion履歴を保持 |
| seed | 実装済み | 小規模で安定したコードマスターのvendor値を保持 |
| `stg_` | 実装済み | snake_case、型変換、同一source内の重複排除 |
| `int_` | 一部実装 | J-QuantsとYahooの日次価格統合・source優先順位 |
| `mart_` | 未実装 | 分析者向けの日足・ファンダメンタル指標 |

stagingモデル名は`stg_<source>__<entity>`とし、sourceとentityの境界を二重underscoreで表します。

## 重要な前提

- J-Quantsを最終的な正本、Yahoo Financeを直近期間の暫定補完として扱います。
- stagingではJ-QuantsとYahooを統合しません。source間の優先順位はintermediateで実装します。
- rawに同じbusiness keyの再取得履歴があるため、stagingは`_ingested_at`降順の先頭を採用します。
- `stg_yahoo__daily_bars.adjusted_close`はYahooから取得した値です。共通の価格調整系列はintermediateで作成します。
- canonical日次価格はJ-Quants行を優先し、Yahoo-only行を`is_provisional=true`として保持します。
- YahooのOHLC・出来高は原則split調整済みとして扱い、splitイベントを再適用しません。
- 財務値の通貨・単位はJ-Quantsの提供仕様に従います。このレイヤーでは換算しません。

## モデルの探し方

source非依存の日次価格は`int_stock__daily_prices`を参照してください。source別の日足は`stg_jquants__daily_bars`と`stg_yahoo__daily_bars`、銘柄属性は`stg_jquants__equity_master`と`stg_jpx__listed_issues`、財務・決算予定は`stg_jquants__financial_summary`と`stg_jquants__earnings_date`を参照します。業種・市場区分のコードマスターは`stg_jquants__sector_17`、`stg_jquants__sector_33`、`stg_jquants__market_segments`を参照します。

各モデルページにはgrain、列定義、data test、上流sourceとのlineageを掲載しています。

{% enddocs %}
