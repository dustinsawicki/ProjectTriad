"""Smoke tests — run via `pytest -q` from src/api/."""


def test_settings_imports() -> None:
    from app import schemas  # noqa: F401


def test_safe_json_parses_fences() -> None:
    from app.services.orchestrator import _safe_json

    assert _safe_json('{"a": 1}') == {"a": 1}
    assert _safe_json('```json\n{"b": 2}\n```') == {"b": 2}
    assert _safe_json("prose then {\"c\":3} more").get("c") == 3
