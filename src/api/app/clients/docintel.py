"""Azure AI Document Intelligence client for PDF extraction."""

from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.identity import DefaultAzureCredential

from app.config import settings


def _get_client() -> DocumentIntelligenceClient:
    credential = DefaultAzureCredential()
    return DocumentIntelligenceClient(
        endpoint=settings.DOCINTEL_ENDPOINT,
        credential=credential,
    )


def extract_document(blob_url: str, model_id: str = "prebuilt-document") -> dict[str, Any]:
    """Extract structured fields from a PDF at the given blob URL."""
    client = _get_client()
    poller = client.begin_analyze_document(
        model_id=model_id,
        analyze_request={"urlSource": blob_url},
        content_type="application/json",
    )
    result = poller.result()

    # Extract key-value pairs
    kv_pairs = {}
    if result.key_value_pairs:
        for pair in result.key_value_pairs:
            key = pair.key.content if pair.key else None
            value = pair.value.content if pair.value else None
            if key:
                kv_pairs[key] = value

    # Extract tables
    tables = []
    if result.tables:
        for table in result.tables:
            rows = []
            for cell in table.cells:
                while len(rows) <= cell.row_index:
                    rows.append({})
                rows[cell.row_index][f"col_{cell.column_index}"] = cell.content
            tables.append(rows)

    return {
        "model_id": model_id,
        "content": result.content[:2000] if result.content else None,
        "key_value_pairs": kv_pairs,
        "tables": tables,
        "page_count": len(result.pages) if result.pages else 0,
    }


def extract_invoice(blob_url: str) -> dict[str, Any]:
    """Extract fields from a medical bill or estimate using prebuilt-invoice."""
    return extract_document(blob_url, model_id="prebuilt-invoice")
