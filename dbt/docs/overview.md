{% docs __overview__ %}

# stock-analytics

東証上場銘柄の価格・銘柄属性・財務・決算予定を、分析しやすい形へ整えるdbt projectです。

## データフロー

```text
J-Quants ─┐
Yahoo     ├─ raw_* ─ stg_* ─ int_* ─ mart_*
JPX      ─┘
```

現在公開しているのは`stg_*`までです。`raw_*`は取得元の値と再取得履歴を保持し、`stg_*`は列名と型を正規化して、各grainで最新の`_ingested_at`だけを公開します。

## レイヤー責務

| prefix | 状態 | 責務 |
|---|---|---|
| `raw_` | 実装済み | 取得元別の値とingestion履歴を保持 |
| `stg_` | 実装済み | snake_case、型変換、同一source内の重複排除 |
| `int_` | 未実装 | J-QuantsとYahooの価格調整・source優先順位 |
| `mart_` | 未実装 | 分析者向けの日足・ファンダメンタル指標 |

stagingモデル名は`stg_<source>__<entity>`とし、sourceとentityの境界を二重underscoreで表します。

## 重要な前提

- J-Quantsを最終的な正本、Yahoo Financeを直近期間の暫定補完として扱います。
- stagingではJ-QuantsとYahooを統合しません。source間の優先順位はintermediateで実装します。
- rawに同じbusiness keyの再取得履歴があるため、stagingは`_ingested_at`降順の先頭を採用します。
- `stg_yahoo__daily_bars.adjusted_close`はYahooから取得した値です。共通の価格調整系列はintermediateで作成します。
- 財務値の通貨・単位はJ-Quantsの提供仕様に従います。このレイヤーでは換算しません。

## モデルの探し方

日足は`stg_jquants__daily_bars`と`stg_yahoo__daily_bars`、銘柄属性は`stg_jquants__equity_master`と`stg_jpx__listed_issues`、財務・決算予定は`stg_jquants__financial_summary`と`stg_jquants__earnings_date`を参照してください。

各モデルページにはgrain、列定義、data test、上流sourceとのlineageを掲載しています。

{% enddocs %}
