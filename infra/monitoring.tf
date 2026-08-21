resource "google_monitoring_notification_channel" "daily_job_email" {
  project      = var.project_id
  display_name = "Stock Analytics daily job email"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.monitoring]
}

resource "google_monitoring_alert_policy" "daily_job_failure" {
  project      = var.project_id
  display_name = "Stock Analytics daily job failure"
  combiner     = "OR"
  enabled      = true

  conditions {
    display_name = "Cloud Run Job error log"

    condition_matched_log {
      filter = join("\n", [
        "resource.type=\"cloud_run_job\"",
        "resource.labels.job_name=\"${local.daily_job_name}\"",
        "severity>=ERROR",
      ])
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.daily_job_email.name
  ]

  alert_strategy {
    auto_close = "604800s"
    notification_rate_limit {
      period = "300s"
    }
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The stock analytics daily Cloud Run Job emitted an error. Check the matching Cloud Logging entry and the latest Job execution."
  }

  depends_on = [
    google_project_service.logging,
    google_project_service.monitoring,
    google_cloud_run_v2_job.daily,
  ]
}
