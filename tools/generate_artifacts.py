#!/usr/bin/env python3
"""Regenerate controls/policies/data.json and docs/*-mapping.md AUTOGEN
blocks from controls/unified_controls.csv.

Run `python tools/generate_artifacts.py`, then `git diff --exit-code` in CI
to fail the build if committed output is stale relative to the CSV.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "controls" / "unified_controls.csv"
VERSION_PATH = REPO_ROOT / "controls" / "CATALOG_VERSION"
DATA_JSON_PATH = REPO_ROOT / "controls" / "policies" / "data.json"
DOCS_DIR = REPO_ROOT / "docs"

DOC_FRAMEWORK_COLUMN = {
    "nist-ai-rmf-mapping.md": "NIST AI RMF",
    "eu-ai-act-mapping.md": "EU AI Act",
    "owasp-llm-top10-mapping.md": "OWASP LLM Top 10 (2025)",
    "iso-42001-mapping.md": "ISO/IEC 42001",
}

AUTOGEN_START = "<!-- AUTOGEN:START -->"
AUTOGEN_END = "<!-- AUTOGEN:END -->"
BLOCK_PATTERN = re.compile(
    re.escape(AUTOGEN_START) + r".*?" + re.escape(AUTOGEN_END), re.DOTALL
)


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        return [row for row in csv.DictReader(fh) if row.get("ID", "").strip()]


def build_data_json(rows: list[dict[str, str]], version: str) -> dict:
    """Pure computation of the data.json payload from CSV rows + catalog version."""
    required = sorted(
        row["ID"].strip()
        for row in rows
        if row.get("Enforced in CI", "").strip().lower() == "yes"
    )
    return {"required_controls": required, "catalog_version": version}


def write_data_json(rows: list[dict[str, str]]) -> None:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    data = build_data_json(rows, version)
    DATA_JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def render_table(rows: list[dict[str, str]], column: str) -> str:
    lines = ["| Control | Citation |", "| --- | --- |"]
    for row in rows:
        citation = row.get(column, "").strip()
        if not citation or citation == "—":
            continue
        lines.append(f"| {row['ID'].strip()} {row['Control'].strip()} | {citation} |")
    return "\n".join(lines)


def update_doc(filename: str, column: str, rows: list[dict[str, str]]) -> None:
    path = DOCS_DIR / filename
    text = path.read_text(encoding="utf-8")
    if not BLOCK_PATTERN.search(text):
        raise SystemExit(f"{path}: missing {AUTOGEN_START}/{AUTOGEN_END} markers")
    block = f"{AUTOGEN_START}\n{render_table(rows, column)}\n{AUTOGEN_END}"
    path.write_text(BLOCK_PATTERN.sub(block, text), encoding="utf-8")


def main() -> int:
    rows = load_rows()
    write_data_json(rows)
    for filename, column in DOC_FRAMEWORK_COLUMN.items():
        update_doc(filename, column, rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
