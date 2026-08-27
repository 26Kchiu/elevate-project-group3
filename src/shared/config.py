"""Configuration settings for Elevate HR System & BigQuery Knowledge Layer."""
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Centralized configuration settings."""
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "elevate-taiwan-cohort-2")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "US")
    model_name: str = os.getenv("MODEL_NAME", "gemini-3.7-flash")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-005")
    
    # BigQuery Knowledge & Graph Layer
    bq_knowledge_dataset: str = "hr_knowledge"
    bq_analytics_dataset: str = "hr_analytics"
    bq_property_graph_name: str = "hr_knowledge.hr_policy_graph"
    gcs_policy_corpus_bucket: str = "hr-policy-corpus"
    
    # Curation SLAs
    curation_band_a_threshold: float = 0.85
    curation_band_b_threshold: float = 0.65
    curation_band_c_threshold: float = 0.45
    publication_sla_hours: int = 4
    withdrawal_sla_minutes: int = 15


settings = Settings()
