# データモデルと品質上の注意

このプロジェクトは、JPX、J-Quants、Yahoo FinanceのデータをBigQueryの`stock_analytics` datasetへ格納し、dbtで分析用の形へ統合します。sourceごとに提供時期や企業行動の扱いが異なるため、同じ銘柄・取引日でも値が完全には一致しないことがあります。

## データsource

### JPX

現行の上場銘柄一覧を取得し、銘柄コード、銘柄名、Yahoo tickerなどの対応付けに使用します。価格sourceではありません。

### J-Quants

日次価格の確定sourceとして使用します。未調整OHLC・出来高に加え、`AdjFactor`と調整済みOHLC・出来高を保持します。利用planに伴う提供遅延があるため、直近期間にはJ-Quantsデータがまだ存在しない場合があります。

J-Quantsの調整済み価格は、通常の株式分割・併合だけでなく、ETFの受益権併合や割当などの企業行動を反映することがあります。

### Yahoo Finance

J-Quantsがまだ提供されていない直近期間の暫定価格と、配当・株式分割情報を補完します。Yahoo由来の価格は後日J-Quantsが到着すると置き換えられるため、`is_provisional=true`として識別できます。

Yahooの`Close`とOHLCはvendor側で分割調整されることがありますが、銘柄や企業行動によってJ-Quantsの`AdjC`と同じ基準になるとは限りません。`Adj Close`は配当調整も含み得るため、J-Quantsの分割調整済み終値の代替には使用しません。

## canonical日次価格

`int_stock__daily_prices`は`trade_date, security_code`をgrainとし、次の優先順位で価格を採用します。

1. 同じ銘柄・取引日にJ-QuantsがあればJ-Quantsを採用する。
2. J-QuantsがなければYahoo Financeを暫定採用する。
3. Yahooの配当・株式分割情報は、J-Quants価格を採用する日にも保持する。

主要な診断列は次のとおりです。

| 列 | 意味 |
|---|---|
| `price_source` | canonical価格に採用したsource。`jquants`または`yahoo`。 |
| `is_provisional` | J-Quants未到着のためYahoo価格を暫定採用しているか。 |
| `has_jquants` | 同じ銘柄・取引日のJ-Quants行が存在するか。 |
| `has_yahoo` | 同じ銘柄・取引日のYahoo行が存在するか。 |
| `jquants_close` | J-Quantsの未調整終値。 |
| `yahoo_close` | Yahooが返した終値。 |
| `jquants_split_adjusted_close` | J-Quantsの企業行動調整済み終値。 |
| `yahoo_split_adjusted_close` | Yahooの`Close`を分割調整済みとして保持した値。 |
| `close_relative_difference` | J-Quants未調整終値とYahoo終値の相対差。 |
| `split_adjusted_close_relative_difference` | 両sourceの調整済み扱いの終値を比較した相対差。 |

## source間の価格差

実データでは、大部分の重複価格は高い精度で一致します。一方、次の理由で1%を超える差が継続するケースがあります。

- J-Quantsだけが企業行動を`AdjFactor`へ反映している。
- J-QuantsとYahooで株式分割・併合の倍率または適用時期が異なる。
- ETFの受益権併合などがYahooの`Stock Splits`に存在しない。
- Yahoo側に10倍、100倍などの一時的な価格異常がある。
- IPO直後や流動性の低い銘柄でvendor間の値が一致しない。

Yahooの`Close`がJ-Quantsの未調整`C`と一致する一方、J-Quantsの`AdjC`とは大きく異なるケースもあります。そのため、`split_adjusted_close_relative_difference`だけでsourceの正誤を決定できません。

## dbtの品質判定

次のようなcanonicalデータ自身の破損はhard failureとして扱い、pipelineを停止します。

- business keyの重複
- 必須列のnull
- 価格・出来高の不正な範囲
- J-Quants優先規則や暫定フラグの破綻

source間の価格差は、データ提供者の調整基準の違いだけでも発生するためwarningとして扱います。

- 相対差0.1%超: 通常warning
- 相対差1%超: 大幅差warning

warningはCloud Run Jobを失敗させません。件数の急増や新しい極端値は調査対象ですが、既知のvendor差が日次取得・BigQuery load・他のdbt model更新を停止させない設計です。

## 利用時の注意

- 確定済み期間の分析では、原則として`price_source='jquants'`を使用します。
- 直近期間で`is_provisional=true`の価格は、後日J-Quants到着時に変わる可能性があります。
- source間差分列はデータ品質の診断用であり、売買シグナルとして直接使用しません。
- Yahooだけに存在する極端値を分析へ使用する場合は、周辺日や別sourceとの比較が必要です。
