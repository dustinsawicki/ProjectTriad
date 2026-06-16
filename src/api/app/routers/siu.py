"""SIU (Special Investigations Unit) router — link-graph API for the visualization."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Any

from app.clients.cosmos import get_link_graph_neighbors
from app.db import get_session

router = APIRouter(prefix="/api/siu", tags=["siu"])


@router.get("/graph")
async def get_graph(
    claim: str = Query(..., description="Claim ID or claim number"),
    s: Session = Depends(get_session),
) -> dict[str, Any]:
    """Return nodes and edges for the link-graph neighborhood of a claim's parties."""
    result = s.execute(
        text("SELECT CAST(Id AS NVARCHAR(36)) FROM Party WHERE ClaimId = :claim"),
        {"claim": claim},
    )
    party_ids = [row[0] for row in result.fetchall()]

    if not party_ids:
        return {"nodes": [], "edges": []}

    # Gather edges from all parties
    all_edges = []
    for pid in party_ids:
        edges = get_link_graph_neighbors(pid, hops=2)
        all_edges.extend(edges)

    # Deduplicate edges
    seen_edges = set()
    unique_edges = []
    for e in all_edges:
        if e["id"] not in seen_edges:
            seen_edges.add(e["id"])
            unique_edges.append(e)

    # Extract nodes
    node_ids = set()
    for e in unique_edges:
        node_ids.add(e["from"])
        node_ids.add(e["to"])

    nodes = [
        {
            "id": nid,
            "label": nid.replace("party:", ""),
            "is_focus": nid.replace("party:", "") in party_ids,
        }
        for nid in node_ids
    ]

    edges = [
        {
            "id": e["id"],
            "from": e["from"],
            "to": e["to"],
            "type": e["type"],
            "weight": e.get("weight", 1.0),
            "label": e.get("evidence", {}).get("shared_value", e["type"]),
        }
        for e in unique_edges
    ]

    return {"nodes": nodes, "edges": edges}
