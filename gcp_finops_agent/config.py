"""Application configuration."""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Configuration loaded from environment variables."""

    gcp_project_id: str = Field(default="", validation_alias="GCP_PROJECT_ID")
    gcp_location: str = Field(default="us-central1", validation_alias="GCP_LOCATION")
    gemini_model: str = Field(default="gemini-2.5-flash", validation_alias="GEMINI_MODEL")
    gcp_project_scope_raw: str = Field(default="", validation_alias="GCP_PROJECT_SCOPE")
    gcp_billing_dataset: str = Field(default="", validation_alias="GCP_BILLING_DATASET")
    gcp_detailed_billing_dataset: str = Field(default="", validation_alias="GCP_DETAILED_BILLING_DATASET")
    a2a_executor_enabled: bool = Field(default=False, validation_alias="A2A_EXECUTOR_ENABLED")
    a2a_executor_resource_name: str = Field(default="", validation_alias="A2A_EXECUTOR_RESOURCE_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Ignore extra env vars (e.g., ADK-specific GOOGLE_* vars)
    )

    @property
    def gcp_project_scope(self) -> list[str]:
        """Return parsed list of project IDs from comma-separated string."""
        if not self.gcp_project_scope_raw:
            return []
        return [item.strip() for item in self.gcp_project_scope_raw.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return a cached Config instance.

    Lazy loading avoids import-time failures during packaging/deployment where
    runtime environment variables may not be available yet.
    """

    return Config()
