"""Azure Blob Storage client for photos and documents."""

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings


def _get_client() -> BlobServiceClient:
    credential = DefaultAzureCredential()
    return BlobServiceClient(
        account_url=settings.BLOB_ENDPOINT,
        credential=credential,
    )


def list_blobs(container_name: str, prefix: str) -> list[str]:
    """List blob names under a prefix."""
    client = _get_client()
    container = client.get_container_client(container_name)
    return [b.name for b in container.list_blobs(name_starts_with=prefix)]


def get_blob_content(container_name: str, blob_name: str) -> bytes:
    """Download blob content."""
    client = _get_client()
    blob = client.get_blob_client(container_name, blob_name)
    return blob.download_blob().readall()


def generate_read_sas_url(container_name: str, blob_name: str, ttl_minutes: int = 10) -> str:
    """Generate a SAS URL with read-only access for a blob."""
    credential = DefaultAzureCredential()
    # Use user delegation key for SAS
    blob_service = BlobServiceClient(
        account_url=settings.BLOB_ENDPOINT, credential=credential
    )
    delegation_key = blob_service.get_user_delegation_key(
        key_start_time=datetime.now(timezone.utc),
        key_expiry_time=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    sas_token = generate_blob_sas(
        account_name=settings.BLOB_ACCOUNT_NAME,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )
    return f"{settings.BLOB_ENDPOINT}{container_name}/{blob_name}?{sas_token}"


def upload_blob(container_name: str, blob_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload data to a blob and return the URL."""
    client = _get_client()
    blob = client.get_blob_client(container_name, blob_name)
    blob.upload_blob(data, overwrite=True, content_settings={"content_type": content_type})
    return f"{settings.BLOB_ENDPOINT}{container_name}/{blob_name}"
