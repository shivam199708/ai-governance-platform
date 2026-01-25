"""Configuration management for the AI Governance Platform"""
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # Gemini API Configuration (Google AI Studio)
    gemini_api_key: Optional[str] = None  # Your Google AI Studio API key
    gemini_model: str = "gemini-3-flash-preview"  # Gemini 3 Flash Preview
    gemini_temperature: float = 0.1

    # GCP Configuration (for BigQuery and optional Vertex AI)
    project_id: str = "your-gcp-project-id"
    location: str = "us-central1"

    # BigQuery Configuration
    bigquery_dataset: str = "ai_governance"
    bigquery_audit_table: str = "audit_logs"

    # API Configuration
    api_title: str = "AI Governance Platform"
    api_version: str = "0.1.0"
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
