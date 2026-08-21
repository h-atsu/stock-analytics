data "google_secret_manager_secret" "jquants_api_key" {
  project   = var.project_id
  secret_id = "jquants-api-key"
}

resource "google_secret_manager_secret_iam_member" "daily_job_accessor" {
  project   = var.project_id
  secret_id = data.google_secret_manager_secret.jquants_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.daily_job.email}"

  depends_on = [google_project_service.secret_manager]
}
