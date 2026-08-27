"""Configuration settings for Elevate HR System."""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    model_name: str = os.getenv("MODEL_NAME", "gemini-2.5-flash")
