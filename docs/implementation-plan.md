# 東証株価分析基盤 実装計画

最終更新日: 2026-08-15

## 進め方

- 各タスクは「設計確認 → 1タスクだけ実装 → 検証 → この計画を更新 → 停止」の順で進める。
- 次のタスクへ自動的に進まない。実装前にユーザーと設計を確認する。
- YAGNIを優先し、実際の重複や要件が生じるまで基底クラス、汎用リポジトリ、dataset registry、プラグイン構造を作らない。
- 新しいセッションでは、最初にこのファイルと`git status`を確認する。
- ユーザーの未コミット変更は保持し、対象タスクと無関係なファイルを変更しない。

## アーキテクチャ

J-Quantsを最終的な正本、Yahoo Financeを直近期間の暫定データとして扱う。

```text
J-Quants ─────── raw_jquants ─┐
                               ├─ staging ─ intermediate ─ mart_stock_daily
Yahoo Finance ─ raw_yfinance ─┘                  │
                                                 └─ J-Quants優先で自動差し替え
JPX銘柄一覧 ──── raw_jpx ────── 銘柄コード・Yahoo ticker対応
```

- 同一銘柄・取引日に両方の価格が存在する場合はJ-Quantsを採用する。
- 後日J-Quantsデータが到着したら、dbtの再実行だけでYahoo由来の行を置き換える。
- rawではベンダー値を加工せず、価格調整とsource precedenceはdbtで処理する。
- Yahoo Financeは個人・研究用途の暫定補完に限定する。

## 確定したインターフェース

既存CLI:

```text
stock-analytics ingest daily-bars --date YYYY-MM-DD
```

追加予定CLI:

```text
stock-analytics ingest listed-issues
stock-analytics ingest yahoo-daily-bars --start-date YYYY-MM-DD --end-date YYYY-MM-DD
stock-analytics ingest equity-master --date YYYY-MM-DD
stock-analytics ingest financial-summary --date YYYY-MM-DD
stock-analytics ingest earnings-date --date YYYY-MM-DD
stock-analytics backfill --start-date YYYY-MM-DD --end-date YYYY-MM-DD
stock-analytics pipeline daily --as-of YYYY-MM-DD
```

yfinanceの取得条件は実装内の固定値から開始し、不要なCLIオプションは増やさない。

- `interval="1d"`
- `auto_adjust=False`
- `actions=True`
- `keepna=True`
- 100 ticker単位で逐次取得
- 一時エラーは2秒、4秒、8秒で最大3回リトライ
- 日次処理は直近7暦日をローリング再取得
- 初回はJ-Quantsと同じ約2年分を取得
- `end`は排他的として扱う

## 現在のデータ契約

### J-Quants株価日足

- API endpoint: `/equities/bars/daily`
- dataset名: `equity_daily_bars`
- Panderaの`DailyBars` `DataFrameModel`で検証する。
- 実行時の取引日制約だけ`daily_bars_model(trade_date)` factoryで追加する。
- factoryを呼ぶだけの薄い検証関数は作らない。
- 入力列はstrictとし、未知の列をエラーにする。
- `Code`は数字または英大文字からなる5文字とする。
- `(Date, Code)`を一意キーとする。
- `Date`は要求した取引日と一致させる。
- 出来高、売買代金、時価総額、調整後出来高は、値がある場合は0以上とする。
- `AdjFactor`は0より大きい値とする。
- 高値は安値以上、調整後高値は調整後安値以上とする。
- 売買がない行を表現できるよう、OHLC、出来高などの市場値はnullableとする。
- 空のDataFrameは受け付けない。休場日などのno-dataを正常終了にする変更は日次パイプライン設計時に別途判断する。

### ローカル保存

保存先はrun単位の追記型とする。

```text
<output-root>/equity_daily_bars/
  trade_date=YYYY-MM-DD/
    ingested_at=YYYYMMDDTHHMMSS.ffffffZ/
      data.parquet
      manifest.json
```

- `ingested_at`はtimezone-awareで受け取り、UTCへ正規化する。
- Parquetには`_ingested_at`と`_source`を付加する。
- `Date`はParquet保存時に日付型へ変換する。
- Parquetとmanifestは一時ファイルを書いてからatomic replaceする。
- 同一の`ingested_at` partitionは上書きせずエラーにする。
- manifestにはdataset、trade date、UTC ingestion time、row count、source、schema version、ParquetのSHA-256を保存する。

### Task 1検証結果

2026-08-15時点の基準状態:

- `uv run pytest`: 11件成功
- `uv run ruff check .`: 成功
- `uv run ty check`: 成功
- 既存実装は上記契約を満たしているため、Task 1でPythonコードは変更していない。
- `pyproject.toml`と`uv.lock`にあるyfinance追加は、Task 0開始前から存在するユーザー変更として保持した。

## タスク一覧

### Task 0: 計画をリポジトリへ保存 — 完了

- 本計画を`docs/implementation-plan.md`へ保存する。
- タスクの状態、設計判断、検証結果を別セッションから参照可能にする。

完了条件: 新しいセッションがこのファイルから次の1タスクを判断できること。

### Task 1: 既存日足ingestionの契約を確定 — 完了

- J-Quants日足、Pandera、Parquet、manifestの現行仕様を確定する。
- 動的な取引日検証にはschema factoryを使う。
- 薄い転送ラッパーを追加しない。

完了条件: 現行チェックがすべて通り、契約がこのファイルに記録されていること。

### Task 2: J-Quants銘柄マスター取得 — 完了

- 上場銘柄情報を日次スナップショットとして取得する。
- Pandera `DataFrameModel`で型、コード、一意性を検証する。
- 既存日足と同じParquet・manifest規約で保存する。

完了条件: 任意日付の銘柄マスターを取得でき、再実行可能であること。

実装・検証結果（2026-08-15）:

- V2 `/equities/master`の13列を`EquityMaster` `DataFrameModel`で検証する。
- 実行時の基準日制約は`equity_master_model(snapshot_date)` factoryで追加する。
- `(Date, Code)`を一意キーとし、数字・英大文字からなる5桁コードを受け付ける。
- 業種、市場、信用区分のaccepted valuesはraw schemaで固定しない。
- `equity_master/snapshot_date=YYYY-MM-DD/ingested_at=...`へParquetとmanifestを保存する。
- CLIは`stock-analytics ingest equity-master --date YYYY-MM-DD`とする。
- 自動テスト18件、Ruff、tyが成功した。
- 実APIで2024-07-25時点の4,378行を取得・検証・一時保存できた。

### Task 3: J-Quants財務サマリー取得 — 完了

- 財務情報を開示日単位で取得する。
- rawでは欠損を許容し、型と一意性を検証する。
- ファンダメンタル指標はまだ計算しない。

完了条件: 財務サマリーをParquetへ保存し、fixtureテストが通ること。

実装・検証結果（2026-08-15）:

- V2 `/fins/summary`を開示日単位で取得する。
- Freeプランで利用可能な日付取得に`get_fin_summary_cursor`をcursorなしで使用し、deprecated APIを避ける。
- sourceの全111列が存在することを確認する。
- 識別列と期間列を`FinancialSummary` `DataFrameModel`で型検証する。
- `(DiscDate, Code, DiscNo)`を一意キーとする。
- 予想来期期間と財務数値の欠損をrawでは許容する。
- 財務数値の型変換と指標計算はdbtへ委ねる。
- `financial_summary/disclosure_date=YYYY-MM-DD/ingested_at=...`へ保存する。
- CLIは`stock-analytics ingest financial-summary --date YYYY-MM-DD`とする。
- 自動テスト25件、Ruff、tyが成功した。
- 実APIで2024-07-25開示分の43行・111列を取得、検証、一時保存できた。

### Task 4: セクター・市場区分マスター — 完了

- 安定した小規模マスターはdbt seedで管理する。
- 汎用マスター管理層は作らない。

完了条件: seedの一意性・not nullテストが通ること。

実装・検証結果（2026-08-15）:

- 最小のdbtプロジェクトを`dbt/`へ作成した。
- `sector_17`、`sector_33`、`market_segments`の3 seedを追加した。
- コード列はBigQueryで`string`になるよう明示し、先頭ゼロを保持する。
- コードのunique/not null、名称のnot nullをdata testとして定義した。
- 33業種の`sector_17_code`から17業種seedへのrelationships testを定義した。
- J-Quants同梱コード表の英語名称にある末尾空白と明らかな欠字だけを正規化した。
- dbt 1.12.2で3 seeds、14 data testsをparse・選択できた。
- CSVは17業種18行、33業種34行、市場区分10行で、一意性・非空・参照整合性を確認した。
- BigQueryへの`dbt seed`とdata testの実行は、GCP環境構築後に行う。

### Task 4.5: 決算発表予定日取得 — 完了

- `/fins/earnings-date`を公表日単位で取得する。
- rawでは予定日の変更・未定を含む履歴をすべて保持する。
- 最新予定日の導出はdbt intermediateで行う。

完了条件: 公表日単位の決算予定日を検証し、Parquetとmanifestへ保存できること。

実装・検証結果（2026-08-15）:

- 7列をstrictな`EarningsDate` `DataFrameModel`で検証する。
- `(PubDate, Code, FQName)`を一意キーとする。
- 実行時の公表日制約は`earnings_date_model(publication_date)` factoryで追加する。
- 予定日未定を表現するため`SchDate`はnullableとする。
- `earnings_date/publication_date=YYYY-MM-DD/ingested_at=...`へ保存する。
- CLIは`stock-analytics ingest earnings-date --date YYYY-MM-DD`とする。
- 自動テスト31件、Ruff、format、ty、dbt parseが成功した。
- 実APIで2024-07-25公表分の20行を取得、検証、一時保存できた。
- Freeの遅延があるため、直近の決算回避ではなく履歴分析用として扱う。

### Task 5: JPX現行上場銘柄一覧の取得 — 完了

- JPX公式Excelの原本と正規化Parquetを保存する。
- 日次確認し、SHA-256が変わった場合だけ新スナップショットを保存する。
- ETF、REIT等を除外せず、東証上場商品をすべて対象にする。
- JPXコードからYahoo ticker候補を生成する。

完了条件: 同じ公式ファイルから重複スナップショットが作られないこと。

実装・検証結果（2026-08-15）:

- JPX公式ページのHTMLから現在の`data_j.xls` URLを発見して取得する。
- Excel原本、正規化Parquet、manifestを月末スナップショットとして保存する。
- source ExcelのSHA-256が保存済みの場合は`unchanged=true`で終了する。
- 10列の公式データをsnake_caseへ正規化し、`-`をnullへ変換する。
- 33業種コードはdbt seedと結合できる4桁文字列へゼロ埋めする。
- `JpxListedIssues` `DataFrameModel`で列、型、コード一意性、単一基準日を検証する。
- 4桁英数字コードには`{security_code}.T`をYahoo ticker候補として付与する。
- 5桁の種類株式は別銘柄への誤対応を避けるためYahoo tickerをnullにする。
- `.xls`読込の直接依存として`xlrd`を追加した。
- 自動テスト40件、Ruff、format、ty、dbt parseが成功した。
- 実データで2026-07-31時点の4,444銘柄を保存し、同一ファイルの再取得がskipされることを確認した。

### Task 6: yfinance日足・コーポレートアクション取得 — 完了

- JPX一覧のYahoo ticker候補がある銘柄を対象に、100 ticker単位で日足、配当、株式分割を取得する。
- raw OHLC、volume、`Adj Close`、dividend、stock splitを日付別Parquetへ保存する。
- responseにないtickerはcoverage結果へ`no_data`として記録する。
- 通信失敗は3回リトライ後に非ゼロ終了する。
- `BaseIngestor`やdataset registryは作らない。

完了条件: 複数銘柄、配当、分割、欠損tickerを処理できること。

実装・検証結果（2026-08-16）:

- 最新のJPX listed-issues Parquetからnon-nullのYahoo ticker候補を読み込む。
- 100 ticker単位のバッチは逐次実行し、各バッチ内は`threads=True`で取得する。
- `auto_adjust=False`、`actions=True`、`keepna=True`、`repair=False`を固定する。
- CLIの開始日・終了日は包含とし、yfinanceの排他的endには1日加算して渡す。
- 通信例外は2秒、4秒、8秒の待機で最大3回リトライする。
- MultiIndexレスポンスを日付・ticker単位へ正規化する。
- raw OHLC、`adj_close`、volume、dividend、stock split、capital gainsを保持する。
- `YahooDailyBars` `DataFrameModel`で日付、ticker、型、一意性、high/lowを検証する。
- 日足は`equity_daily_bars/trade_date=.../ingested_at=...`へ保存する。
- ticker別の`available`・`no_data`と有効行数をrange単位のcoverage Parquetへ保存する。
- `stock-analytics ingest yahoo-daily-bars --start-date ... --end-date ...`を追加した。
- 自動テスト50件、Ruff、format、ty、dbt parseが成功した。
- 実APIで株式2銘柄とETF 1銘柄の6営業日、計18行を取得・検証・一時保存できた。
- 100銘柄・2年分の実測で`threads=True`は13.6秒、`threads=False`は23.4秒だったため、バッチ内のスレッド並列を有効化した。
- Yahoo Financeは個人・研究用途の暫定sourceとして扱い、J-Quants到着後に置換する。

### Task 7: 本番Dockerイメージ — 完了

- Cloud Run Jobと同じイメージをローカル実行可能にする。
- `.env`をイメージに含めない。
- CLIをentrypointにする。
- devcontainerは具体的な必要性が出るまで追加しない。

完了条件: 少数銘柄の取得からParquet保存までコンテナ内で動くこと。

実装・検証結果（2026-08-16）:

- Python 3.12.13 slimとuv 0.11.19を固定し、`uv.lock`に基づく本番依存だけをinstallする`Dockerfile`を追加した。
- `stock-analytics`をentrypointにし、Cloud Run JobでCLI引数をそのまま指定できる形にした。
- `.dockerignore`で`.env`、`data`、`.git`、テスト、notebook、dbt生成物をbuild contextから除外した。
- uvのダウンロードキャッシュとbytecodeをイメージに残さず、ローカルイメージサイズを3.1GBから1.5GBへ削減した。
- READMEにbuild、CLI起動、`.env`と出力ディレクトリの実行時mount手順を追加した。
- イメージ内に`/app/.env`と`/app/data`が存在しないことを確認した。
- 最終イメージで`7203.T`の2026-08-10から2026-08-14を実取得し、4行の日足を4個の日別Parquetとcoverageへ保存できた。
- devcontainerは追加していない。

### Task 8: Terraform bootstrap — 実装済み（apply待ち）

- Terraform state用GCS bucketは初回だけ手動作成し、Artifact RegistryをTerraformで作る。
- dev単一環境、手動apply、手動イメージpushから始める。

完了条件: 空のGCPプロジェクトから`terraform init/plan/apply`を再現できること。

実装・検証結果（2026-08-16）:

- dev/prod directory、workspace、共通moduleは作らず、`infra/`直下の単一root moduleとした。
- Terraform state用GCS bucketはbootstrap前提としてgcloudで一度だけ手動作成し、Terraform管理対象外とした。
- state bucketはversioning、uniform bucket-level access、public access prevention、7日間のsoft deleteを有効にする。
- Terraform 1.15.xとGoogle provider 7.41.xを指定し、Artifact Registry APIとDocker用repositoryを定義した。
- GCS backendの`stock-analytics` prefixで1つのstateを使用する。
- `terraform.tfvars`、local state、plan fileはGit管理対象外にした。
- GCS backend接続を除くoffline検証で`terraform validate`とダミーprojectへの`terraform plan -refresh=false`が成功し、2 resources add、0 change、0 destroyを確認した。
- gcloudの既定projectが未設定のため、state bucket作成、GCS backend初期化、実プロジェクトへのplan/applyは未実施。

### Task 9: データ基盤Terraform — 着手（BigQuery・raw GCS実装済み）

- raw用GCS bucketを作る。
- BigQueryは`stock_analytics`単一datasetから始め、raw・staging・intermediate・martsはテーブル名で区別する。
- Secret Manager、service account、最小権限IAM、Cloud Run Job、Cloud Schedulerを作る。
- ローカルは`.env`、Cloud RunはSecret Managerを利用する。

完了条件: secret値がstateやコードに含まれず、IAMが必要最小限であること。

実装・検証結果（2026-08-16、途中）:

- BigQuery APIとTokyoリージョン（`asia-northeast1`）の`stock_analytics` datasetをTerraformに追加した。
- datasetはraw tableとdbt modelで共用し、`raw_`、`stg_`、`int_`、`dim_`、`fct_`の命名でレイヤーを区別する。
- `delete_contents_on_destroy=false`とし、テーブルがあるdatasetの誤削除を防止する。
- dbt用service accountとdataset IAMはCloud Run Jobの実行主体と合わせて後続実装する。
- GCS backend接続を除くoffline検証で`terraform validate`と`terraform plan -refresh=false`が成功し、Task 8分を含め4 resources add、0 change、0 destroyを確認した。
- 検証済みraw artifact用にTokyoリージョンの`${project_id}-stock-analytics-raw` GCS bucketを追加した。
- raw bucketはuniform bucket-level access、public access prevention、7日間のsoft delete、`force_destroy=false`を設定する。
- raw objectは`ingested_at`付きのimmutable pathに保存するため、bucket versioningと自動削除は現時点で追加しない。
- raw GCS追加後のoffline Terraform planは合計6 resources add、0 change、0 destroyで成功した。

### Task 10: GCS publishとBigQuery load — 着手（GCS publish実装済み）

- 検証済みParquetだけをGCSへuploadする。
- rawテーブルは`trade_date` partition、`security_code` clusterとする。
- 同一キーの再取得で論理的な重複を作らない。
- 最初はsourceごとの明示的処理を書き、汎用loaderを作らない。

完了条件: 同一日付を2回loadしても重複しないこと。

実装・検証結果（2026-08-16、途中）:

- `data/raw`配下の`data.parquet`と対応する`manifest.json`だけを検出し、local rootからの相対pathをGCS object名としてpublishする。
- publish前に全ParquetのSHA-256をmanifestと照合し、1つでも不一致またはmanifest欠落があれば送信を開始せず失敗する。
- `if_generation_match=0`で既存objectを上書きせず、再実行時はskip件数に計上する。
- JPXの`source.xls`など、Parquet・manifest以外のファイルはpublish対象外とする。
- `stock-analytics publish raw --bucket ... --source-dir data/raw`を追加した。
- `google-cloud-storage` 3.1.1以上を直接依存として明示した。
- GCS publishの自動テスト3件とCLIテスト1件が成功した。
- 実bucket `${project_id}-stock-analytics-raw` へのpublishが成功することを確認した。

### Task 11: dbt staging — 未着手

- source freshness、not null、unique、accepted valuesを定義する。
- source別に列名、型、security codeを正規化する。
- 同一source・銘柄・日付は最新の`_ingested_at`を採用する。

完了条件: rawから正規化済みstagingを`dbt build`で再現できること。

### Task 12: dbt intermediateとcanonical価格 — 未着手

- Yahooのsplitからsplit-adjusted OHLC/volumeを計算する。
- J-Quantsは提供されたadjusted列を使う。
- 同一銘柄・日付ではJ-Quantsを優先する。
- J-Quants後着時にdbt再実行だけでYahoo行を置き換える。
- 当初はincrementalを使わず、table再構築で運用する。
- overlapでraw close、split-adjusted close、volume、corporate actionを比較する。
- 相対価格差0.1%超をwarning、1%超をerrorとする。
- 決算予定履歴から銘柄・決算期ごとの最新予定日を導出する。

完了条件: source片側、両側、後着、split、dividendのdbtテストが通ること。

### Task 13: 最小マート — 未着手

- `mart_stock_daily`を作る。
- raw価格、split-adjusted価格、price return、total returnを区別する。
- `price_source`、`corporate_action_source`、`is_provisional`を持たせる。
- ファンダメンタル指標とポートフォリオ分析はまだ実装しない。

完了条件: 分析側がsource固有列を意識せず日足を参照できること。

### Task 14: 初回バックフィル — 未着手

- J-QuantsとYahooを約2年分取得する。
- JPX現行一覧、銘柄マスター、財務サマリー、決算予定履歴も取得する。
- 成功済み日次ファイルをskipして中断後に再開可能にする。
- checkpoint管理基盤は作らない。

完了条件: 再実行可能で、J-QuantsとYahooの重複比較を確認できること。

### Task 15: 日次パイプライン — 未着手

`pipeline daily --as-of`で次を直列実行する。

1. JPX一覧のハッシュを確認する。
2. J-Quantsの`as-of - 84日`付近の日足、財務サマリー、決算予定履歴を取得する。
3. Yahooの`as-of - 7日`から`as-of`まで再取得する。
4. Panderaで検証する。
5. GCSへuploadする。
6. BigQueryへloadする。
7. `dbt build`を実行する。

Asia/Tokyoを基準にする。休場日やno-dataは正常なno-opとし、検証失敗は後続へ渡さない。

完了条件: 固定した`as-of`でローカルとCloud Run Jobの結果が一致すること。

### Task 16: Cloud Run Jobと運用確認 — 未着手

- 平日21時JSTに単一Cloud Run Jobを起動する。
- 初期値は2 vCPU、4 GiB、最大60分、Scheduler retry最大3回とする。
- 件数、対象期間、source、所要時間、欠損ticker数を構造化ログへ出す。
- 初回backfillは手動Job実行にする。
- Cloud Logging alertで失敗を通知する。

完了条件: 日次実行、再実行、欠損ticker、J-Quants後着、secret参照をGCP上で確認できること。

## 全体テスト方針

- Pandera: 型、キー重複、日付範囲、価格・出来高制約
- ingestion: 正常、空、pagination、欠損、通信失敗のfixtureテスト
- Yahoo: MultiIndex、英数字コード、ETF/REIT、配当、分割、no-data ticker
- dbt: unique、not null、relationships、source precedence、後着差し替え
- finance: 2-for-1 split、現金配当、splitと配当の同日発生
- idempotency: 同一期間を複数回実行して行数が増えない
- container: secretをイメージへ含めずCLIを実行できる
- Terraform: `fmt`、`validate`、`plan`

## 現時点で対象外

- Airflow、Workflows、Pub/Sub、Dataflow
- devcontainer
- CI/CDによる自動deploy
- 複数Cloud Run Jobへの分割
- ファンダメンタルスコア
- ロバストポートフォリオ
- ダッシュボード

これらは`mart_stock_daily`の品質確認後に必要性を再評価する。
