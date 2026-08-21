resource "google_cloud_scheduler_job" "daily" {
  project     = var.project_id
  region      = var.region
  name        = "stock-analytics-daily"
  description = "Run the stock analytics daily Cloud Run Job on weekdays"
  schedule    = var.daily_job_schedule
  time_zone   = "Asia/Tokyo"

  attempt_deadline = "180s"

  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "3600s"
    max_doublings        = 3
  }

  http_target {
    http_method = "POST"
    uri = join("", [
      "https://run.googleapis.com/v2/projects/",
      var.project_id,
      "/locations/",
      var.region,
      "/jobs/",
      google_cloud_run_v2_job.daily.name,
      ":run",
    ])
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode("{}")

    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [
    google_project_service.cloud_scheduler,
    google_cloud_run_v2_job_iam_member.scheduler_invoker,
  ]
}
