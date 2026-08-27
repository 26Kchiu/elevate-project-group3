# Cloud Run Service for Google ADK Agent Application
resource "google_cloud_run_v2_service" "agent_service" {
  name     = "hr-policy-agent-app"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    scaling {
      min_instance_count = 1
      max_instance_count = 10
    }

    containers {
      image = "gcr.io/${var.project_id}/hr-policy-agent:v2.0.0"

      resources {
        limits = {
          cpu    = "2"
          memory = "4Gi"
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "DEFAULT_MODEL"
        value = "gemini-3.7-flash"
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
    }

    service_account = google_service_account.agent_sa.email
  }
}
