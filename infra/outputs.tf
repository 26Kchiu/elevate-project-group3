output "cloud_run_service_url" {
  value       = google_cloud_run_v2_service.agent_service.uri
  description = "Cloud Run service URL for HR Policy Agent application"
}

output "bigquery_knowledge_dataset" {
  value       = google_bigquery_dataset.knowledge_dataset.dataset_id
  description = "BigQuery Knowledge dataset ID"
}

output "audit_events_topic" {
  value       = google_pubsub_topic.audit_events.name
  description = "Pub/Sub topic for audit event stream"
}
