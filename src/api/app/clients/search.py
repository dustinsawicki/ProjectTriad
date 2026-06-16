"""Azure AI Search client for RAG over historical claims."""

from typing import Any

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizableTextQuery

from app.config import settings


def _get_client() -> SearchClient:
    credential = DefaultAzureCredential()
    return SearchClient(
        endpoint=settings.SEARCH_ENDPOINT,
        index_name=settings.SEARCH_INDEX_NAME,
        credential=credential,
    )


def search_historical(
    query_text: str,
    loss_type: str | None = None,
    state: str | None = None,
    kind: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid search (BM25 + vector + semantic) over the historical-claims index."""
    client = _get_client()

    # Build filter
    filters = []
    if loss_type:
        filters.append(f"loss_type eq '{loss_type}'")
    if state:
        filters.append(f"state eq '{state}'")
    if kind:
        filters.append(f"kind eq '{kind}'")
    filter_expr = " and ".join(filters) if filters else None

    # Vector query using integrated vectorization
    vector_query = VectorizableTextQuery(
        text=query_text,
        k_nearest_neighbors=top_k,
        fields="body_vector",
    )

    results = client.search(
        search_text=query_text,
        vector_queries=[vector_query],
        filter=filter_expr,
        top=top_k,
        query_type="semantic",
        semantic_configuration_name="default",
        select=["id", "kind", "title", "body", "loss_type", "state", "settled_amount", "settled_date"],
    )

    output = []
    for r in results:
        output.append({
            "id": r["id"],
            "kind": r.get("kind"),
            "title": r.get("title"),
            "body_snippet": (r.get("body") or "")[:300],
            "loss_type": r.get("loss_type"),
            "state": r.get("state"),
            "settled_amount": r.get("settled_amount"),
            "settled_date": r.get("settled_date"),
            "score": r.get("@search.score"),
        })
    return output
