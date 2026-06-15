"""Index historical markdown corpus into Azure AI Search."""
from __future__ import annotations

import argparse
import json
import os
import random
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import numpy as np
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.storage.blob import BlobServiceClient
from faker import Faker
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

SEED = 42
random.seed(SEED)
Faker.seed(SEED)
fake = Faker("en_US")
fake.seed_instance(SEED)
RNG = np.random.default_rng(SEED)
INDEX_NAME = "historical-claims"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blob-account-name", default=os.getenv("BLOB_ACCOUNT_NAME"))
    parser.add_argument("--search-endpoint", default=os.getenv("SEARCH_ENDPOINT"))
    parser.add_argument("--foundry-project-endpoint", default=os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
    parser.add_argument("--reseed", action="store_true")
    args = parser.parse_args(argv)
    for field in ("blob_account_name", "search_endpoint", "foundry_project_endpoint"):
        if not getattr(args, field):
            parser.error(f"{field.replace('_', '-')} is required.")
    return args


def _blob_service(account_name: str) -> BlobServiceClient:
    return BlobServiceClient(account_url=f"https://{account_name}.blob.core.windows.net", credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))


def _parse_markdown(text: str) -> tuple[dict[str, str], str]:
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    metadata: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata, parts[2].strip()


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    tokens = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        chunk_tokens = tokens[start:start + chunk_size]
        chunks.append(" ".join(chunk_tokens))
        if start + chunk_size >= len(tokens):
            break
        start += chunk_size - overlap
    return chunks


def _project_client(endpoint: str) -> AIProjectClient:
    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=1, max=30), retry=retry_if_exception_type(Exception), reraise=True)
def _embed_texts(project_client: AIProjectClient, texts: list[str]) -> list[list[float]]:
    inference = getattr(project_client, "inference", None)
    if inference is None:
        raise RuntimeError("AIProjectClient.inference is unavailable in this azure-ai-projects version.")
    if hasattr(inference, "get_embeddings"):
        response = inference.get_embeddings(model="text-embedding-3-large", input=texts)
        return [item.embedding for item in response.data]
    embeddings = getattr(inference, "embeddings", None)
    if embeddings and hasattr(embeddings, "embed"):
        response = embeddings.embed(model="text-embedding-3-large", input=texts)
        data = getattr(response, "data", response)
        return [item.embedding if hasattr(item, "embedding") else item["embedding"] for item in data]
    raise RuntimeError("Unsupported azure-ai-projects embeddings client surface.")


def _ensure_index(endpoint: str) -> None:
    credential = DefaultAzureCredential(exclude_interactive_browser_credential=False)
    client = SearchIndexClient(endpoint=endpoint, credential=credential)
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="kind", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="body", type=SearchFieldDataType.String),
        SearchField(name="body_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), searchable=True, vector_search_dimensions=3072, vector_search_profile_name="body-vector-profile"),
        SimpleField(name="loss_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="state", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="settled_amount", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="settled_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
    ]
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-cosine")],
        profiles=[VectorSearchProfile(name="body-vector-profile", algorithm_configuration_name="hnsw-cosine")],
    )
    semantic_search = SemanticSearch(
        configurations=[SemanticConfiguration(name="default", prioritized_fields=SemanticPrioritizedFields(title_field=SemanticField(field_name="title"), content_fields=[SemanticField(field_name="body")]))]
    )
    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search, semantic_search=semantic_search)
    client.create_or_update_index(index)


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=1, min=1, max=30), retry=retry_if_exception_type(Exception), reraise=True)
def _upload_batch(search_client: SearchClient, docs: list[dict[str, Any]]) -> None:
    search_client.upload_documents(documents=docs)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[index_historical] Deterministic seed={SEED}")
    _ensure_index(args.search_endpoint)
    project_client = _project_client(args.foundry_project_endpoint)
    blob_container = _blob_service(args.blob_account_name).get_container_client("historical")
    docs_to_upload: list[dict[str, Any]] = []
    for blob in blob_container.list_blobs():
        payload = blob_container.download_blob(blob.name).readall().decode("utf-8")
        metadata, body = _parse_markdown(payload)
        chunks = _chunk_text(body)
        embeddings = _embed_texts(project_client, chunks)
        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True), start=1):
            docs_to_upload.append(
                {
                    "id": f"{blob.name.replace('/', '-')}-{chunk_index}",
                    "kind": metadata.get("kind", "unknown"),
                    "title": metadata.get("title", blob.name),
                    "body": chunk,
                    "body_vector": embedding,
                    "loss_type": metadata.get("loss_type", "unknown"),
                    "state": metadata.get("state", "NA"),
                    "settled_amount": float(metadata.get("settled_amount", 0.0)),
                    "settled_date": metadata.get("settled_date", datetime.now(UTC).date().isoformat()),
                }
            )
    search_client = SearchClient(endpoint=args.search_endpoint, index_name=INDEX_NAME, credential=DefaultAzureCredential(exclude_interactive_browser_credential=False))
    for index in range(0, len(docs_to_upload), 16):
        _upload_batch(search_client, docs_to_upload[index:index + 16])
    summary = {"generator": "index_historical", "chunks": len(docs_to_upload), "index": INDEX_NAME}
    print(f"SUMMARY {json.dumps(summary, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
