# Cloud Pub/Sub Topics for Audit Events and Dead-Letter Queue
resource "google_pubsub_topic" "audit_events" {
  name = "hr-agent-audit-events"
}

resource "google_pubsub_topic" "audit_dlq" {
  name = "hr-agent-audit-dlq"
}

resource "google_pubsub_subscription" "audit_bq_sub" {
  name  = "hr-agent-audit-bq-subscription"
  topic = google_pubsub_topic.audit_events.id

  bigquery_config {
    table               = "${var.project_id}.${var.analytics_dataset_id}.audit_events_v1"
    use_topic_schema    = false
    write_metadata      = true
  }

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.audit_dlq.id
    max_delivery_attempts = 5
  }
}
