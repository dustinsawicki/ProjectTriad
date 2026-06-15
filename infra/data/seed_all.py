"""Run every v2 Claims PoC data generator in dependency order."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

SEED = 42
SCRIPT_DIR = Path(__file__).resolve().parent
GENERATOR_ORDER: list[tuple[str, str]] = [
    ("1", "gen_sql.py"),
    ("2", "gen_blob_photos.py"),
    ("3", "gen_blob_pdfs.py"),
    ("4", "gen_telematics.py"),
    ("5", "gen_link_graph.py"),
    ("6", "gen_feature_store.py"),
    ("7", "gen_historical_corpus.py"),
    ("8", "index_historical.py"),
    ("9", "gen_external_apis.py"),
    ("10", "replay_telematics.py"),
]


@dataclass(slots=True)
class RunResult:
    order: str
    script_name: str
    status: str
    summary: dict[str, object]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python executable to use for child generators.")
    parser.add_argument("--reseed", action="store_true", help="Force generators to clear their targets before inserting.")
    return parser.parse_args(argv)


def _extract_summary(output: str, script_name: str) -> dict[str, object]:
    for line in reversed(output.splitlines()):
        if line.startswith("SUMMARY "):
            payload = line.removeprefix("SUMMARY ").strip()
            data = json.loads(payload)
            if isinstance(data, dict):
                return data
    return {"generator": script_name.removesuffix('.py'), "note": "No summary payload emitted."}


def run_generator(order: str, script_name: str, python_executable: str, reseed: bool) -> RunResult:
    command = [python_executable, str(SCRIPT_DIR / script_name)]
    if reseed:
        command.append("--reseed")
    print(f"[seed_all] ({order}/10) Running {script_name} ...")
    completed = subprocess.run(command, cwd=SCRIPT_DIR, capture_output=True, text=True, check=False)
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("
") else "
")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("
") else "
")
    status = "ok" if completed.returncode == 0 else f"failed ({completed.returncode})"
    summary = _extract_summary(completed.stdout, script_name)
    summary.setdefault("exit_code", completed.returncode)
    return RunResult(order=order, script_name=script_name, status=status, summary=summary)


def print_summary_table(results: list[RunResult]) -> None:
    print("
[seed_all] Summary")
    headers = ("Step", "Generator", "Status", "Key metrics")
    rows: list[tuple[str, str, str, str]] = []
    for result in results:
        summary = {k: v for k, v in result.summary.items() if k not in {"generator", "exit_code"}}
        metrics = ", ".join(f"{k}={v}" for k, v in summary.items()) or "-"
        rows.append((result.order, result.script_name, result.status, metrics))

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def fmt(row: tuple[str, str, str, str] | tuple[str, str, str, str]) -> str:
        return " | ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row))

    print(fmt(headers))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(fmt(row))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    print(f"[seed_all] Deterministic seed={SEED}")
    results = [run_generator(order, script_name, args.python, args.reseed) for order, script_name in GENERATOR_ORDER]
    print_summary_table(results)
    failed = [result for result in results if not result.status.startswith("ok")]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
