# Secret Manager Vault for Confirmation Keys & Upstream Credentials
resource "google_secret_manager_secret" "confirmation_secret" {
  secret_id = "hr-agent-confirmation-hmac-key"
  replication {
    auto {}
  }
}
