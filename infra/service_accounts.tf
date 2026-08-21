resource "google_service_account" "daily_job" {
  project      = var.project_id
  account_id   = "stock-analytics-daily"
  display_name = "Stock Analytics daily Cloud Run Job"

  depends_on = [google_project_service.iam]
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "stock-analytics-scheduler"
  display_name = "Stock Analytics Cloud Scheduler invoker"

  depends_on = [google_project_service.iam]
}

resource "google_storage_bucket_iam_member" "daily_job_raw_viewer" {
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.daily_job.email}"
}

resource "google_storage_bucket_iam_member" "daily_job_raw_creator" {
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.daily_job.email}"
}

resource "google_project_iam_member" "daily_job_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.daily_job.email}"
}

resource "google_bigquery_dataset_iam_member" "daily_job_data_editor" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.stock_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.daily_job.email}"
}
