from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. Populated by Container Apps."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # SQL
    sql_server_fqdn: str
    sql_database_name: str

    # Entra
    azure_tenant_id: str
    azure_client_id: str | None = None  # for local dev only

    # Foundry
    foundry_project_endpoint: str
    foundry_model_deployment: str = "gpt-4o"
    foundry_mini_model_deployment: str = "gpt-4o-mini"

    # Key Vault
    key_vault_name: str | None = None

    # App
    adjuster_user_object_ids: str = ""  # CSV
    log_level: str = "INFO"

    # Telemetry
    applicationinsights_connection_string: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
