# Infrastructure

単一のGoogle Cloudプロジェクトを1つのTerraform root moduleで管理します。Terraformが利用するstate bucketだけは、プロジェクトと同じく事前に手動作成します。

## 前提

- Billingと紐付いた空のGoogle Cloudプロジェクト
- Terraform 1.15.x
- gcloud CLI
- Terraformを実行するアカウントの必要なIAM権限

ローカルではサービスアカウントキーを作らず、Application Default Credentialsを利用します。

```bash
gcloud auth application-default login
```

## 初回セットアップ

プロジェクトIDを設定し、Terraform state用GCS bucketを一度だけ手動作成します。

```bash
export STOCK_ANALYTICS_PROJECT_ID="YOUR_GCP_PROJECT_ID"

gcloud services enable \
  serviceusage.googleapis.com \
  storage.googleapis.com \
  --project "$STOCK_ANALYTICS_PROJECT_ID"

gcloud storage buckets create \
  "gs://${STOCK_ANALYTICS_PROJECT_ID}-terraform-state" \
  --project "$STOCK_ANALYTICS_PROJECT_ID" \
  --location ASIA-NORTHEAST1 \
  --uniform-bucket-level-access \
  --public-access-prevention \
  --soft-delete-duration 7d

gcloud storage buckets update \
  "gs://${STOCK_ANALYTICS_PROJECT_ID}-terraform-state" \
  --versioning
```

続いてTerraformを初期化します。

```bash
cd infra
cp ../.env.example ../.env
# terraform.tfvarsのproject_idを変更する

terraform init \
  -backend-config="bucket=${STOCK_ANALYTICS_PROJECT_ID}-terraform-state"
terraform plan -out=terraform.tfplan
terraform apply terraform.tfplan
```

`.env`、state、planはGit管理対象外です。`apply`前にplan内容を確認してください。

## 日次Cloud Run Jobのセットアップ

Terraformの実行前に、GCPコンソールのSecret Managerで`jquants-api-key`を作成し、有効なversionへJ-Quants APIキーを登録します。Secret本体と値はTerraformで管理せず、既存secretをdata sourceとして参照します。

repository rootの`.env`へproject ID、region、通知先を設定します。miseがTerraform用の`TF_VAR_*`へ変換するため、`infra/terraform.tfvars`は使用しません。

```dotenv
GCP_PROJECT_ID=stock-analytics-505614
GCP_REGION=asia-northeast1
ALERT_EMAIL=you@example.com
```

初回はCloud Run Jobが参照するimageを先にArtifact Registryへpushします。

```bash
gcloud auth configure-docker asia-northeast1-docker.pkg.dev

IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/stock-analytics/stock-analytics:latest"
docker buildx build --platform linux/amd64 --tag "$IMAGE" --push ..
```

準備後は1回のplanとapplyで、API、service account、IAM、Cloud Run Job、Scheduler、監視を作成します。

```bash
mise run plan-infra
mise run apply-infra
```

作成される日次処理:

- Cloud Run Job `stock-analytics-daily`: 2 vCPU、4 GiB、timeout 60分、task retryなし
- Cloud Scheduler `stock-analytics-daily`: 平日21:00、Asia/Tokyo、起動API失敗時は最大3回retry
- J-Quants APIキー: Secret Managerの`latest` versionを環境変数へ注入
- Cloud Logging: 対象JobのERROR logを検知し、指定メールへ通知

SchedulerのretryはCloud Run起動API自体の失敗に対するものです。起動後のpipeline失敗は重複取得を避けるため自動再実行せず、alert確認後に次のコマンドで手動再実行します。

```bash
gcloud run jobs execute stock-analytics-daily \
  --project "$GCP_PROJECT_ID" \
  --region "$GCP_REGION" \
  --wait
```

初回apply後、Google Cloudから届く通知channel確認メールでメールアドレスをverifyしてください。

dbtやアプリを更新するときは、commit SHAなどの一意なimage tagでbuild・pushし、`daily_job_image_tag`を指定してapplyします。同じ`latest`をpushし直すだけではCloud Run Jobの更新をTerraformが検知できません。
