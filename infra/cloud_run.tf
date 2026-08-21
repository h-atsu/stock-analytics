locals {
  daily_job_name = "stock-analytics-daily"
  daily_job_image = join("", [
    google_artifact_registry_repository.docker.location,
    "-docker.pkg.dev/",
    var.project_id,
    "/",
    google_artifact_registry_repository.docker.repository_id,
    "/",
    var.daily_job_image_name,
    ":",
    var.daily_job_image_tag,
  ])
}

resource "google_cloud_run_v2_job" "daily" {
  project             = var.project_id
  name                = local.daily_job_name
  location            = var.region
  deletion_protection = false

  labels = {
    application = "stock-analytics"
    managed_by  = "terraform"
    workload    = "daily-pipeline"
  }

  template {
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.daily_job.email
      timeout         = "3600s"
      max_retries     = 0

      containers {
        image = local.daily_job_image
        args = [
          "pipeline",
          "daily",
          "--project",
          var.project_id,
          "--bucket",
          google_storage_bucket.raw_data.name,
          "--dataset",
          google_bigquery_dataset.stock_analytics.dataset_id,
          "--region",
          var.region,
          "--structured-logs",
        ]

        env {
          name = "JQUANTS_API_KEY"
          value_source {
            secret_key_ref {
              secret  = data.google_secret_manager_secret.jquants_api_key.secret_id
              version = "latest"
            }
          }
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
      }
    }
  }

  depends_on = [
    google_project_service.cloud_run,
    google_secret_manager_secret_iam_member.daily_job_accessor,
    google_storage_bucket_iam_member.daily_job_raw_creator,
    google_storage_bucket_iam_member.daily_job_raw_viewer,
    google_project_iam_member.daily_job_bigquery_job_user,
    google_bigquery_dataset_iam_member.daily_job_data_editor,
  ]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = google_cloud_run_v2_job.daily.location
  name     = google_cloud_run_v2_job.daily.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
