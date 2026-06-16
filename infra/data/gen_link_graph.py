"""Generate the fraud-link graph in Cosmos DB."""
from __future__ import annotations

import argparse
import json
import os
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
from azure.cosmos import CosmosClient, PartitionKey
from azure.identity import DefaultAzureCredential
from faker import Faker

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = SCRIPT_DIR / ".seed_state" / "gen_sql_output.json"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cosmos-endpoint", default=os.getenv("COSMOS_ENDPOINT"))
    parser.add_argument("--cosmos-database", default=os.getenv("COSMOS_DATABASE"))
    parser.add_argument("--manifest-path", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    if not args.cosmos_endpoint or not args.cosmos_database:
        parser.error("COSMOS_ENDPOINT and COSMOS_DATABASE are required.")
    return args


def _cosmos_container(args: argparse.Namespace):
    client = CosmosClient(args.cosmos_endpoint, credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))
    database = client.create_database_if_not_exists(id=args.cosmos_database)
    return database.create_container_if_not_exists(id="link_graph", partition_key=PartitionKey(path="/state"))


def _load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Run gen_sql.py first; manifest not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _clear_existing(container) -> int:
    deleted = 0
    for item in container.query_items("SELECT c.id, c.state FROM c WHERE c.source = 'seed_v2'", enable_cross_partition_query=True):
        container.delete_item(item=item["id"], partition_key=item["state"])
        deleted += 1
    return deleted


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[gen_link_graph] Deterministic seed={SEED}")
    manifest = _load_manifest(args.manifest_path)
    claims_by_ring = {}
    for claim in manifest["claims"]:
        if claim["ring_id"]:
            claims_by_ring.setdefault(claim["ring_id"], []).append(claim)
    parties_by_ring = {}
    for party in manifest["ring_parties"]:
        parties_by_ring.setdefault(party["ring_id"], []).append(party)

    graph = nx.MultiGraph(seed=SEED)
    for ring in manifest["fraud_rings"]:
        state = ring["shared_address"]["state"]
        claim_nodes = [f"claim:{claim['claim_number']}" for claim in claims_by_ring.get(ring["ring_id"], [])]
        party_nodes = [f"party:{party['party_id']}" for party in parties_by_ring.get(ring["ring_id"], [])]
        nodes = claim_nodes + party_nodes
        for node in nodes:
            graph.add_node(node, state=state, ring_id=ring["ring_id"])
        for edge_type in ("shared_phone", "shared_address", "shared_vin"):
            for left_index, left in enumerate(nodes):
                for right in nodes[left_index + 1:]:
                    graph.add_edge(left, right, edge_type=edge_type, state=state, ring_id=ring["ring_id"])

    container = _cosmos_container(args)
    deleted = _clear_existing(container)
    print(f"[gen_link_graph] Cleared {deleted} existing edges")
    records: list[dict[str, Any]] = []
    for edge_index, (left, right, attrs) in enumerate(graph.edges(data=True)):
        records.append(
            {
                "id": f"edge-{edge_index:05d}",
                "source": "seed_v2",
                "fromId": left,
                "toId": right,
                "edgeType": attrs["edge_type"],
                "ringId": attrs["ring_id"],
                "state": attrs["state"],
                "weight": round(float(RNG.uniform(0.75, 0.99)), 3),
            }
        )
    records.sort(key=lambda item: (item["state"], item["edgeType"], item["fromId"], item["toId"]))
    records = records[:2000]
    for record in records:
        container.upsert_item(record)
    summary = {"generator": "gen_link_graph", "edges": len(records), "rings": len(manifest["fraud_rings"])}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
