"""Idempotent registration of Foundry agents from JSON definitions.

Call `ensure_agents()` once at startup. Uses the new Foundry Agent Service
`create_version()` API with `PromptAgentDefinition` — agents are versioned
by name and can be referenced in the Responses API via `agent_reference`.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition
from azure.identity import DefaultAzureCredential

from ..config import get_settings

log = logging.getLogger(__name__)

AGENTS_DIR = Path(__file__).resolve().parent

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
    """Register all four agents using Foundry Agent Service create_version().

    Returns {agent_name: agent_name} — agent_name is the key used
    in `agent_reference` when calling `responses.create()`.
    """
    client = get_project_client()
    out: dict[str, str] = {}

    for name in AGENT_NAMES:
        defn = _load_def(name)
        model = os.environ.get(
            defn.get("model_env", "FOUNDRY_MODEL_DEPLOYMENT"),
            get_settings().foundry_model_deployment,
        )
        try:
            client.agents.create_version(
                agent_name=name,
                definition=PromptAgentDefinition(
                    model=model,
                    instructions=defn["instructions"],
                    tools=defn.get("tools", []),
                ),
            )
            log.info("Registered agent version: %s (model=%s)", name, model)
        except Exception as e:  # noqa: BLE001
            log.warning("Agent registration for %s failed (may already exist): %s", name, e)

        out[name] = name
    return out
