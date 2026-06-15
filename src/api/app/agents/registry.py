"""Idempotent registration of Foundry agents from JSON definitions.

Call `ensure_agents()` once at startup. Agents are keyed by `name`; if an agent
with the same name exists, its instructions/tools are updated in place.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from ..config import get_settings

log = logging.getLogger(__name__)

AGENTS_DIR = Path(__file__).resolve().parent

# These names must match the `name` field in each JSON definition.
AGENT_NAMES = (
    "FnolDocumentAgent",
    "TriageCoverageAgent",
    "AssessmentSettlementAgent",
    "GuardrailsAgent",
)


@lru_cache(maxsize=1)
def get_project_client() -> AIProjectClient:
    s = get_settings()
    return AIProjectClient(endpoint=s.foundry_project_endpoint, credential=DefaultAzureCredential())


def _load_def(name: str) -> dict[str, Any]:
    path = AGENTS_DIR / f"{_filename_for(name)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _filename_for(name: str) -> str:
    return {
        "FnolDocumentAgent": "fnol_agent",
        "TriageCoverageAgent": "triage_agent",
        "AssessmentSettlementAgent": "assessment_agent",
        "GuardrailsAgent": "guardrails_agent",
    }[name]


def ensure_agents() -> dict[str, str]:
    """Register all four agents idempotently. Returns {agent_name: agent_id}."""
    client = get_project_client()
    out: dict[str, str] = {}
    try:
        existing = {a.name: a.id for a in client.agents.list_agents()}
    except Exception as e:  # pragma: no cover
        log.warning("Could not list existing agents (cold project?): %s", e)
        existing = {}

    for name in AGENT_NAMES:
        defn = _load_def(name)
        model = os.environ.get(defn.get("model_env", "FOUNDRY_MODEL_DEPLOYMENT"), get_settings().foundry_model_deployment)
        if name in existing:
            agent_id = existing[name]
            client.agents.update_agent(
                agent_id=agent_id,
                model=model,
                instructions=defn["instructions"],
                tools=defn.get("tools", []),
            )
            log.info("Updated agent %s (%s)", name, agent_id)
        else:
            created = client.agents.create_agent(
                model=model,
                name=name,
                instructions=defn["instructions"],
                tools=defn.get("tools", []),
            )
            agent_id = created.id
            log.info("Created agent %s (%s)", name, agent_id)
        out[name] = agent_id
    return out
