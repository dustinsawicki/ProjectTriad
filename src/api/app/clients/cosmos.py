"""Cosmos DB client for telematics, feature store, and link graph."""

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from typing import Any

from app.config import settings


def _get_client() -> CosmosClient:
    credential = DefaultAzureCredential()
    return CosmosClient(url=settings.COSMOS_ENDPOINT, credential=credential)


def get_database():
    client = _get_client()
    return client.get_database_client(settings.COSMOS_DATABASE)


def query_telematics(claim_id: str, start_utc: str, end_utc: str) -> list[dict[str, Any]]:
    """Query telematics events within a time window for a claim."""
    db = get_database()
    container = db.get_container_client("telematics")
    query = (
        "SELECT * FROM c WHERE c.claimId = @claimId "
        "AND c.ts >= @start AND c.ts <= @end "
        "ORDER BY c.ts"
    )
    params = [
        {"name": "@claimId", "value": claim_id},
        {"name": "@start", "value": start_utc},
        {"name": "@end", "value": end_utc},
    ]
    return list(container.query_items(query=query, parameters=params, partition_key=claim_id))


def get_feature(key: str) -> dict[str, Any] | None:
    """Read a feature store entry by key (e.g., 'claim:CLM-200001')."""
    db = get_database()
    container = db.get_container_client("feature_store")
    try:
        return container.read_item(item=key, partition_key=key)
    except Exception:
        return None


def upsert_feature(key: str, features: dict[str, Any]) -> None:
    """Upsert a feature store entry."""
    db = get_database()
    container = db.get_container_client("feature_store")
    container.upsert_item({"id": key, "key": key, "features": features})


def get_link_graph_neighbors(party_id: str, hops: int = 2) -> list[dict[str, Any]]:
    """Get 1- or 2-hop neighbors from the link graph."""
    db = get_database()
    container = db.get_container_client("link_graph")
    # 1-hop
    query = "SELECT * FROM c WHERE c.from = @party OR c.to = @party"
    params = [{"name": "@party", "value": f"party:{party_id}"}]
    edges = list(container.query_items(
        query=query, parameters=params, enable_cross_partition_query=True
    ))

    if hops >= 2:
        # Collect neighbor IDs and query their edges
        neighbor_ids = set()
        for e in edges:
            neighbor_ids.add(e["from"])
            neighbor_ids.add(e["to"])
        neighbor_ids.discard(f"party:{party_id}")

        for nid in list(neighbor_ids):
            query2 = "SELECT * FROM c WHERE c.from = @party OR c.to = @party"
            params2 = [{"name": "@party", "value": nid}]
            hop2 = list(container.query_items(
                query=query2, parameters=params2, enable_cross_partition_query=True
            ))
            edges.extend(hop2)

    # Deduplicate by edge id
    seen = set()
    unique = []
    for e in edges:
        if e["id"] not in seen:
            seen.add(e["id"])
            unique.append(e)
    return unique
