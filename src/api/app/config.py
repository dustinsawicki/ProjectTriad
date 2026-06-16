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
    poc_auth_bypass: bool = False  # Set to true to skip auth for demo

    # Telemetry
    applicationinsights_connection_string: str | None = None

    # v2: Cosmos DB
    cosmos_endpoint: str = ""
    cosmos_database: str = "claims"

    # v2: Blob Storage
    blob_account_name: str = ""
    blob_endpoint: str = ""

    # v2: Event Hubs
    event_hub_namespace_fqdn: str = ""

    # v2: Document Intelligence
    docintel_endpoint: str = ""

    # v2: AI Search
    search_endpoint: str = ""
    search_index_name: str = "historical-claims"

    # v2: External APIs
    external_api_base_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
