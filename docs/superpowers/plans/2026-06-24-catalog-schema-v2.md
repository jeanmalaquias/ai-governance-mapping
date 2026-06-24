# Catalog Schema v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `controls/unified_controls.csv` the actual single source of truth for the Rego policy gate, the per-framework docs, and the compliance-check CLI — and add a risk-tier applicability model so projects don't have to hand-waive every irrelevant control.

**Architecture:** Two new CSV columns (`Enforced in CI`, `Risk Tiers`) plus a `CATALOG_VERSION` file drive everything downstream. A new generator script (`tools/generate_artifacts.py`) turns the CSV into `controls/policies/data.json` (consumed by Rego) and regenerates a marked block inside each `docs/*-mapping.md`. CI runs the generator and fails on diff, so generated output can't silently drift from the CSV again. `aigov.check` gains tier-aware auto-waiving and stamps `catalog_version` into every report.

**Tech Stack:** Python 3.12, pydantic v2, PyYAML, pytest, ruff, OPA (`opa test`), conftest.

**Spec:** [docs/superpowers/specs/2026-06-24-catalog-schema-v2-design.md](../specs/2026-06-24-catalog-schema-v2-design.md)

## Global Constraints

- Python `>=3.12` (per `pyproject.toml`).
- `pydantic>=2.7` — mutable list defaults on `BaseModel` fields are deep-copied per instance; safe to use a literal list default.
- Ruff rule set `E, F, I, UP, B`, line length 88 — all new/modified Python must pass `ruff check .`.
- No embedded commas inside any CSV cell (multi-value cells use `;` as today) — `csv.DictReader` with default dialect must keep working without quoting.
- `compliance-check examples/sample_project.yaml` must keep exiting `0` after every task (it doesn't declare `risk_tier`, so it must keep defaulting to `high` and behaving exactly as today).
- An explicit `status:` declaration in a project's YAML always overrides any tier-derived auto-waiver — never silently drop a human's explicit statement.
- Mappings remain "interpretive aids, not legal advice" — don't strengthen any claim of legal conformance anywhere this plan touches docs/README text.

---

### Task 1: Catalog schema migration — CSV columns, `CATALOG_VERSION`, `Control` model

**Files:**
- Modify: `controls/unified_controls.csv`
- Create: `controls/CATALOG_VERSION`
- Modify: `src/aigov/catalog.py`
- Test: `tests/test_aigov.py`

**Interfaces:**
- Produces: `Control(id: str, control: str, enforced_in_ci: bool = False, risk_tiers: list[str] = ["high", "limited", "minimal"])`; `load_catalog(path: str | Path | None = None) -> list[Control]` (now also populates `enforced_in_ci`/`risk_tiers`); `default_version_path() -> Path`; `load_catalog_version(path: str | Path | None = None) -> str`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_aigov.py` (after `test_catalog_loads_all_controls`):

```python
def test_catalog_parses_enforced_in_ci_and_risk_tiers():
    controls = load_catalog()
    by_id = {c.id: c for c in controls}
    assert by_id["AIGOV-003"].enforced_in_ci is True
    assert by_id["AIGOV-003"].risk_tiers == ["high", "limited", "minimal"]
    assert by_id["AIGOV-001"].enforced_in_ci is False
    assert by_id["AIGOV-001"].risk_tiers == ["high"]


def test_load_catalog_version_reads_repo_file():
    from aigov.catalog import load_catalog_version

    version = load_catalog_version()
    assert version
    assert version.count(".") == 2  # semver-ish, e.g. "1.1.0"


def test_load_catalog_defaults_missing_columns(tmp_path):
    csv_path = tmp_path / "minimal.csv"
    csv_path.write_text("ID,Control\nAIGOV-001,Risk assessment\n", encoding="utf-8")
    controls = load_catalog(csv_path)
    assert controls[0].enforced_in_ci is False
    assert controls[0].risk_tiers == ["high", "limited", "minimal"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aigov.py -k "enforced_in_ci or catalog_version or defaults_missing" -v`
Expected: FAIL — `AttributeError: 'Control' object has no attribute 'enforced_in_ci'` (and `ImportError` for `load_catalog_version`).

- [ ] **Step 3: Migrate the CSV — add the two columns**

Replace the full contents of `controls/unified_controls.csv` with (header gains `Enforced in CI,Risk Tiers`; every row gains the matching two values — semicolon stays the in-cell separator for `Risk Tiers`):

```csv
ID,Control,NIST AI RMF,EU AI Act,OWASP LLM Top 10 (2025),ISO/IEC 42001,Implementation Guidance,Tooling,Evidence Required,Enforced in CI,Risk Tiers
AIGOV-001,AI risk assessment before deployment,GOVERN 1.1; MAP 1.1,Art. 9 (risk management system),—,Clause 6.1; A.5.2,Run and document a risk assessment per use case; re-run on material change,Risk-assessment template; model registry,Signed risk assessment record per release,no,high
AIGOV-002,Data governance and provenance,MAP 2.1; MEASURE 2.2,Art. 10 (data and data governance),LLM04 (Data and Model Poisoning),A.7.2; A.7.3,Track dataset sources licenses and quality; document lineage,Data catalog; DVC; lineage tracking,Dataset datasheet with source and license,no,high
AIGOV-003,Encryption at rest,MANAGE 2.2,Art. 15 (accuracy robustness cybersecurity),LLM02 (Sensitive Information Disclosure),A.6.2.4,Encrypt model artifacts embeddings and stored prompts with managed keys,KMS; envelope encryption,KMS config and at-rest encryption attestation,yes,high;limited;minimal
AIGOV-004,Data retention and minimization,GOVERN 1.2; MAP 3.4,Art. 10; GDPR Art. 5(1)(e),LLM02 (Sensitive Information Disclosure),A.7.2,Define retention windows and purge jobs; collect only what is needed,Retention policy; scheduled purge,Documented retention policy and purge logs,no,high;limited;minimal
AIGOV-005,Human oversight,GOVERN 3.2; MANAGE 4.1,Art. 14 (human oversight),LLM06 (Excessive Agency),A.9.2,Provide a human review and override path for consequential outputs,Approval gates; HITL queue,Review/override audit trail,no,high
AIGOV-006,Prompt-injection and input moderation,MEASURE 2.7; MANAGE 2.3,Art. 15 (cybersecurity),LLM01 (Prompt Injection),A.6.2.6,Run input moderation and injection detection before every model call,Llama Guard; content-safety APIs,Pre-call moderation logs and test results,yes,high;limited;minimal
AIGOV-007,Output handling and content safety,MEASURE 2.6; MANAGE 2.3,Art. 15,LLM05 (Improper Output Handling),A.6.2.6,Moderate and validate outputs; encode/escape before downstream use,Output moderation; schema validation,Post-call moderation and validation logs,yes,high;limited;minimal
AIGOV-008,Transparency and model documentation,GOVERN 1.3; MAP 5.1,Art. 13 (transparency); Art. 11 (technical documentation),LLM09 (Misinformation),A.8.2,Publish a model card covering intended use limits and risks,Model-card generator,Versioned model card per release,no,high
AIGOV-009,Audit logging of AI interactions,MEASURE 1.1; MANAGE 4.1,Art. 12 (record-keeping/logging),LLM01; LLM02,A.6.2.8,Log inputs outputs decisions and overrides with retention; no PII in plaintext,OpenTelemetry; structured logs,Tamper-evident audit log schema and samples,yes,high;limited;minimal
AIGOV-010,Access control and least privilege,GOVERN 1.5,Art. 15 (cybersecurity),LLM06 (Excessive Agency),A.6.2.5,Scope credentials and tool permissions to least privilege per tenant,IAM; OPA; secrets manager,Access policy and periodic access review,yes,high;limited;minimal
AIGOV-011,Evaluation and drift monitoring,MEASURE 2.3; MANAGE 4.1,Art. 15 (accuracy); Art. 72,LLM09 (Misinformation),A.6.2.4; A.6.2.7,Gate releases on eval scores; monitor quality and distribution drift,Eval harness; Evidently AI,Eval reports and drift dashboards,no,high
AIGOV-012,Incident response and post-market monitoring,MANAGE 4.1; MANAGE 4.3,Art. 72 (post-market monitoring); Art. 73 (incident reporting),—,A.6.2.6; A.10,Define AI incident playbooks and a serious-incident reporting path,Alerting; on-call; incident tracker,Incident runbook and post-incident reports,no,high
AIGOV-013,Supply-chain and model provenance,MAP 4.1,Art. 25 (obligations along the value chain),LLM03 (Supply Chain),A.7.3; A.10,Verify third-party model and dependency provenance and integrity,SBOM; signature verification,Model and dependency provenance records,no,high
AIGOV-014,PII detection and sensitive-data handling,MAP 3.4; MEASURE 2.10,Art. 10; GDPR Arts. 5 25,LLM02 (Sensitive Information Disclosure),A.7.2,Detect and redact PII in prompts logs and outputs,PII detection; redaction,PII scan results and redaction config,no,high;limited;minimal
AIGOV-015,Rate limiting and resource controls,MANAGE 2.2,Art. 15 (robustness),LLM10 (Unbounded Consumption),A.6.2.6,Enforce per-tenant rate limits quotas and circuit breakers,API gateway; rate limiter,Rate-limit config and load-test results,yes,high;limited;minimal
AIGOV-016,Bias and fairness testing,MEASURE 2.11; GOVERN 5.1,Art. 10(2)(f) (bias examination),LLM09 (Misinformation),A.6.2.4,Test for disparate performance across groups before and after release,Fairness metrics; eval harness,Fairness test report per release,no,high
```

- [ ] **Step 4: Create `controls/CATALOG_VERSION`**

```
1.1.0
```

(No trailing content beyond the version string and a final newline.)

- [ ] **Step 5: Update `src/aigov/catalog.py`**

Replace the full file with:

```python
"""Load the unified controls catalog from CSV."""

from __future__ import annotations

import csv
from pathlib import Path

from pydantic import BaseModel

DEFAULT_RISK_TIERS = ["high", "limited", "minimal"]


class Control(BaseModel):
    """One catalog control: id, name, and CI/risk-tier applicability metadata."""

    id: str
    control: str
    enforced_in_ci: bool = False
    risk_tiers: list[str] = DEFAULT_RISK_TIERS


def default_catalog_path() -> Path:
    """Path to the bundled unified controls catalog."""
    return Path(__file__).resolve().parents[2] / "controls" / "unified_controls.csv"


def default_version_path() -> Path:
    """Path to the bundled catalog's version file."""
    return default_catalog_path().parent / "CATALOG_VERSION"


def load_catalog(path: str | Path | None = None) -> list[Control]:
    """Load controls from the unified controls CSV (needs ID and Control columns)."""
    csv_path = Path(path) if path else default_catalog_path()
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        controls = []
        for row in reader:
            row_id = row.get("ID", "").strip()
            if not row_id:
                continue
            tiers_raw = row.get("Risk Tiers", "").strip()
            risk_tiers = (
                [t.strip() for t in tiers_raw.split(";") if t.strip()]
                if tiers_raw
                else list(DEFAULT_RISK_TIERS)
            )
            controls.append(
                Control(
                    id=row_id,
                    control=row["Control"].strip(),
                    enforced_in_ci=row.get("Enforced in CI", "").strip().lower()
                    == "yes",
                    risk_tiers=risk_tiers,
                )
            )
        return controls


def load_catalog_version(path: str | Path | None = None) -> str:
    """Read the catalog's semver string from CATALOG_VERSION."""
    version_path = Path(path) if path else default_version_path()
    return version_path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_aigov.py -v`
Expected: all tests PASS, including the 3 new ones and the pre-existing `test_catalog_loads_all_controls` (still 16 controls).

- [ ] **Step 7: Lint**

Run: `ruff check src/aigov/catalog.py tests/test_aigov.py`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add controls/unified_controls.csv controls/CATALOG_VERSION src/aigov/catalog.py tests/test_aigov.py
git commit -m "feat(catalog): add enforced_in_ci/risk_tiers columns and CATALOG_VERSION"
```

---

### Task 2: Risk-tier auto-waiver and `catalog_version` in `check.py`

**Files:**
- Modify: `src/aigov/check.py`
- Test: `tests/test_aigov.py`

**Interfaces:**
- Consumes: `Control` (from Task 1, with `.risk_tiers`), `load_catalog_version()` (from Task 1).
- Produces: `GapReport(project: str, results: list[ControlResult], catalog_version: str = "")`; `evaluate(project: dict, catalog: list[Control] | None = None, catalog_version: str | None = None) -> GapReport`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_aigov.py`:

```python
def test_evaluate_auto_waives_control_outside_declared_tier():
    catalog = [
        Control(id="AIGOV-001", control="Risk assessment", risk_tiers=["high"]),
        Control(
            id="AIGOV-003",
            control="Encryption at rest",
            enforced_in_ci=True,
            risk_tiers=["high", "limited", "minimal"],
        ),
    ]
    project = {
        "name": "Minimal Svc",
        "risk_tier": "minimal",
        "controls": {
            "AIGOV-003": {"status": "satisfied", "evidence": "KMS"},
            # AIGOV-001 omitted: not in scope at risk_tier=minimal
        },
    }
    report = evaluate(project, catalog, catalog_version="9.9.9")
    by_id = {r.id: r for r in report.results}
    assert by_id["AIGOV-001"].state == "waived"
    assert "risk_tier=minimal" in by_id["AIGOV-001"].detail
    assert by_id["AIGOV-003"].state == "satisfied"
    assert report.catalog_version == "9.9.9"


def test_explicit_declaration_overrides_tier_auto_waiver():
    catalog = [Control(id="AIGOV-001", control="Risk assessment", risk_tiers=["high"])]
    project = {
        "risk_tier": "minimal",
        "controls": {
            "AIGOV-001": {"status": "satisfied", "evidence": "risk.md"},
        },
    }
    report = evaluate(project, catalog, catalog_version="9.9.9")
    assert report.results[0].state == "satisfied"
    assert report.results[0].detail == "risk.md"


def test_evaluate_defaults_risk_tier_to_high():
    catalog = [Control(id="AIGOV-001", control="Risk assessment", risk_tiers=["high"])]
    project = {"controls": {}}  # no risk_tier declared
    report = evaluate(project, catalog, catalog_version="9.9.9")
    assert report.results[0].state == "gap"  # high is in scope by default, undeclared -> gap
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aigov.py -k "auto_waives or overrides_tier or defaults_risk_tier" -v`
Expected: FAIL — `TypeError: evaluate() got an unexpected keyword argument 'catalog_version'`.

- [ ] **Step 3: Update `src/aigov/check.py`**

Replace the full file with:

```python
"""Evaluate a project's declared controls against the catalog → gap report."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from .catalog import Control, load_catalog, load_catalog_version


class ControlResult(BaseModel):
    """How one catalog control fared for a project."""

    id: str
    control: str
    state: str  # "satisfied" | "waived" | "gap"
    detail: str = ""


class GapReport(BaseModel):
    """The result of checking a project against the catalog."""

    project: str
    results: list[ControlResult]
    catalog_version: str = ""

    @property
    def gaps(self) -> list[ControlResult]:
        return [r for r in self.results if r.state == "gap"]

    @property
    def has_gaps(self) -> bool:
        return bool(self.gaps)

    def counts(self) -> dict[str, int]:
        counts = {"satisfied": 0, "waived": 0, "gap": 0}
        for r in self.results:
            counts[r.state] += 1
        return counts


def load_project(path: str | Path) -> dict:
    """Load a project config (YAML) describing declared controls."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def _classify(
    declared: dict | None, control: Control, project_tier: str, version: str
) -> tuple[str, str]:
    """Return (state, detail) for one control's declaration."""
    if not declared:
        if project_tier not in control.risk_tiers:
            return (
                "waived",
                f"not applicable at risk_tier={project_tier} (catalog v{version})",
            )
        return "gap", "not addressed"
    status = declared.get("status")
    if status == "satisfied":
        if declared.get("evidence"):
            return "satisfied", str(declared["evidence"])
        return "gap", "marked satisfied but no evidence provided"
    if status == "not_applicable":
        if declared.get("reason"):
            return "waived", str(declared["reason"])
        return "gap", "marked not_applicable but no reason provided"
    return "gap", f"unrecognized status '{status}'"


def evaluate(
    project: dict,
    catalog: list[Control] | None = None,
    catalog_version: str | None = None,
) -> GapReport:
    """Check declared controls against the catalog and produce a gap report."""
    controls = catalog if catalog is not None else load_catalog()
    version = catalog_version if catalog_version is not None else load_catalog_version()
    declared = project.get("controls", {})
    project_tier = project.get("risk_tier", "high")
    results: list[ControlResult] = []
    for control in controls:
        state, detail = _classify(declared.get(control.id), control, project_tier, version)
        results.append(
            ControlResult(
                id=control.id, control=control.control, state=state, detail=detail
            )
        )
    return GapReport(
        project=project.get("name", "unnamed"), results=results, catalog_version=version
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aigov.py -v`
Expected: all tests PASS (old + 3 new). Confirm the pre-existing `test_evaluate_classifies_every_state` and `test_evaluate_flags_bad_status_and_missing_reason` still pass unmodified — both rely on `Control(...)` defaults (`risk_tiers` defaults to all three tiers), so the new tier check never fires for them.

- [ ] **Step 5: Lint**

Run: `ruff check src/aigov/check.py tests/test_aigov.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add src/aigov/check.py tests/test_aigov.py
git commit -m "feat(check): auto-waive controls outside the project's risk tier, stamp catalog_version"
```

---

### Task 3: `catalog_version` in the CLI report

**Files:**
- Modify: `src/aigov/cli.py`
- Test: `tests/test_aigov.py`

**Interfaces:**
- Consumes: `GapReport.catalog_version` (from Task 2).
- Produces: `render(report: GapReport) -> str` (now includes a `catalog version:` line).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_aigov.py`:

```python
def test_render_shows_catalog_version():
    report = GapReport(
        project="P",
        results=[ControlResult(id="AIGOV-001", control="X", state="satisfied", detail="d")],
        catalog_version="1.1.0",
    )
    output = cli.render(report)
    assert "catalog version: 1.1.0" in output
```

Add the needed imports at the top of `tests/test_aigov.py` (alongside the existing `from aigov.check import evaluate, load_project`):

```python
from aigov.check import ControlResult, GapReport, evaluate, load_project
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_aigov.py -k test_render_shows_catalog_version -v`
Expected: FAIL — `assert "catalog version: 1.1.0" in output` (the substring isn't in today's render output).

- [ ] **Step 3: Update `render()` in `src/aigov/cli.py`**

Modify the `render` function (lines 10–23 today):

```python
def render(report: GapReport) -> str:
    counts = report.counts()
    lines = [
        f"# Compliance gap report — {report.project}",
        f"catalog version: {report.catalog_version}",
        "",
        f"satisfied: {counts['satisfied']}  waived: {counts['waived']}  "
        f"gaps: {counts['gap']}",
        "",
        "| control | state | detail |",
        "| --- | --- | --- |",
    ]
    for r in report.results:
        lines.append(f"| {r.id} {r.control} | {r.state} | {r.detail} |")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_aigov.py -v`
Expected: all tests PASS.

- [ ] **Step 5: Lint and full suite**

Run: `ruff check . && pytest --cov --cov-report=term-missing`
Expected: ruff clean; all tests pass; coverage report shows `src/aigov/*` still fully covered.

- [ ] **Step 6: Commit**

```bash
git add src/aigov/cli.py tests/test_aigov.py
git commit -m "feat(cli): show catalog_version in the rendered gap report"
```

---

### Task 4: Generator script — `data.json` for Rego

**Files:**
- Create: `tools/generate_artifacts.py`
- Create: `controls/policies/data.json` (generated by running the script)
- Test: `tests/test_generate_artifacts.py`

**Interfaces:**
- Produces: `controls/policies/data.json` with shape `{"required_controls": list[str], "catalog_version": str}`; module functions `load_rows() -> list[dict[str, str]]`, `write_data_json(rows: list[dict[str, str]]) -> None`.
- Note: this script intentionally does its own lightweight `csv.DictReader` pass instead of importing `aigov.catalog.Control` — it needs every CSV column (including the framework-citation columns used by Task 5), and the package's `Control` model is deliberately kept narrow to what `check.py` needs.

- [ ] **Step 1: Write the failing test**

Create `tests/test_generate_artifacts.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import generate_artifacts as ga  # noqa: E402


FIXTURE_CSV = (
    "ID,Control,NIST AI RMF,EU AI Act,OWASP LLM Top 10 (2025),"
    "ISO/IEC 42001,Implementation Guidance,Tooling,Evidence Required,"
    "Enforced in CI,Risk Tiers\n"
    "AIGOV-001,Risk assessment,GOVERN 1.1,Art. 9,—,Clause 6.1,g,t,e,no,high\n"
    "AIGOV-003,Encryption,MANAGE 2.2,Art. 15,LLM02,A.6.2.4,g,t,e,yes,"
    "high;limited;minimal\n"
)


def test_write_data_json(tmp_path, monkeypatch):
    csv_path = tmp_path / "catalog.csv"
    csv_path.write_text(FIXTURE_CSV, encoding="utf-8")
    version_path = tmp_path / "CATALOG_VERSION"
    version_path.write_text("2.0.0\n", encoding="utf-8")
    out_path = tmp_path / "data.json"

    monkeypatch.setattr(ga, "CSV_PATH", csv_path)
    monkeypatch.setattr(ga, "VERSION_PATH", version_path)
    monkeypatch.setattr(ga, "DATA_JSON_PATH", out_path)

    rows = ga.load_rows()
    ga.write_data_json(rows)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data == {"required_controls": ["AIGOV-003"], "catalog_version": "2.0.0"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_generate_artifacts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'generate_artifacts'`.

- [ ] **Step 3: Create `tools/generate_artifacts.py`**

```python
#!/usr/bin/env python3
"""Regenerate controls/policies/data.json and docs/*-mapping.md AUTOGEN
blocks from controls/unified_controls.csv.

Run `python tools/generate_artifacts.py`, then `git diff --exit-code` in CI
to fail the build if committed output is stale relative to the CSV.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = REPO_ROOT / "controls" / "unified_controls.csv"
VERSION_PATH = REPO_ROOT / "controls" / "CATALOG_VERSION"
DATA_JSON_PATH = REPO_ROOT / "controls" / "policies" / "data.json"


def load_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        return [row for row in csv.DictReader(fh) if row.get("ID", "").strip()]


def write_data_json(rows: list[dict[str, str]]) -> None:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    required = sorted(
        row["ID"].strip()
        for row in rows
        if row.get("Enforced in CI", "").strip().lower() == "yes"
    )
    data = {"required_controls": required, "catalog_version": version}
    DATA_JSON_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    write_data_json(load_rows())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_generate_artifacts.py -v`
Expected: PASS.

- [ ] **Step 5: Generate the real `data.json`**

Run: `python tools/generate_artifacts.py`
Expected: creates `controls/policies/data.json` with content:

```json
{
  "required_controls": [
    "AIGOV-003",
    "AIGOV-006",
    "AIGOV-007",
    "AIGOV-009",
    "AIGOV-010",
    "AIGOV-015"
  ],
  "catalog_version": "1.1.0"
}
```

- [ ] **Step 6: Lint**

Run: `ruff check tools/generate_artifacts.py tests/test_generate_artifacts.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add tools/generate_artifacts.py controls/policies/data.json tests/test_generate_artifacts.py
git commit -m "feat(tools): generate controls/policies/data.json from the catalog CSV"
```

---

### Task 5: Generator script — docs AUTOGEN blocks (fixes the AIGOV-008/NIST drift)

**Files:**
- Modify: `tools/generate_artifacts.py`
- Modify: `docs/nist-ai-rmf-mapping.md`, `docs/eu-ai-act-mapping.md`, `docs/owasp-llm-top10-mapping.md`, `docs/iso-42001-mapping.md`
- Test: `tests/test_generate_artifacts.py`

**Note on scope:** the existing hand-curated tables in these docs are grouped by article/clause/theme (e.g. one EU AI Act row lists 6 control IDs under "Art. 15"). That grouping isn't mechanically derivable from the CSV — it's editorial judgment. Mechanically regenerating *that exact shape* isn't possible without inventing new grouping metadata, which is out of scope (see spec's "Out of scope"). This task instead **replaces** each curated table with a flat, generated `| Control | Citation |` table (one row per CSV row, skipped when that framework's cell is `—`) inside `<!-- AUTOGEN:START -->...<!-- AUTOGEN:END -->` markers. This is the only shape that can be drift-proof, and it directly fixes the missing-AIGOV-008 bug since the table is now produced 1:1 from the CSV rather than hand-maintained. The surrounding prose (source citation, scope notes, GPAI note, etc.) stays hand-written, untouched.

**Interfaces:**
- Consumes: `load_rows()` (from Task 4).
- Produces: `render_table(rows, column) -> str`, `update_doc(filename, column, rows) -> None`, `DOC_FRAMEWORK_COLUMN: dict[str, str]`, `main()` now also regenerates docs.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_generate_artifacts.py`:

```python
def test_render_table_skips_em_dash_and_blank():
    rows = [
        {"ID": "AIGOV-001", "Control": "Risk assessment", "EU AI Act": "Art. 9"},
        {"ID": "AIGOV-009", "Control": "Audit logging", "EU AI Act": "—"},
    ]
    table = ga.render_table(rows, "EU AI Act")
    assert "AIGOV-001 Risk assessment | Art. 9" in table
    assert "AIGOV-009" not in table


def test_update_doc_replaces_only_marked_block(tmp_path, monkeypatch):
    doc_path = tmp_path / "docs"
    doc_path.mkdir()
    target = doc_path / "x-mapping.md"
    target.write_text(
        "# Title\n\nIntro prose.\n\n"
        "<!-- AUTOGEN:START -->\nstale\n<!-- AUTOGEN:END -->\n\nFooter prose.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ga, "DOCS_DIR", doc_path)
    rows = [{"ID": "AIGOV-001", "Control": "Risk assessment", "EU AI Act": "Art. 9"}]

    ga.update_doc("x-mapping.md", "EU AI Act", rows)

    text = target.read_text(encoding="utf-8")
    assert "Intro prose." in text and "Footer prose." in text
    assert "stale" not in text
    assert "AIGOV-001 Risk assessment | Art. 9" in text


def test_update_doc_raises_without_markers(tmp_path, monkeypatch):
    doc_path = tmp_path / "docs"
    doc_path.mkdir()
    target = doc_path / "no-markers.md"
    target.write_text("# Title\n\nNo markers here.\n", encoding="utf-8")
    monkeypatch.setattr(ga, "DOCS_DIR", doc_path)

    with pytest.raises(SystemExit):
        ga.update_doc("no-markers.md", "EU AI Act", [])
```

Add `import pytest` to the top of `tests/test_generate_artifacts.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_generate_artifacts.py -v`
Expected: FAIL — `AttributeError: module 'generate_artifacts' has no attribute 'render_table'`.

- [ ] **Step 3: Extend `tools/generate_artifacts.py`**

Add imports and the new constants/functions, and rewire `main()`:

```python
import re
```

(add alongside the existing `import csv` / `import json` at the top)

```python
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
```

Replace `main()`:

```python
def main() -> int:
    rows = load_rows()
    write_data_json(rows)
    for filename, column in DOC_FRAMEWORK_COLUMN.items():
        update_doc(filename, column, rows)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_generate_artifacts.py -v`
Expected: PASS.

- [ ] **Step 5: Insert AUTOGEN markers into the 4 docs**

In each of `docs/nist-ai-rmf-mapping.md`, `docs/eu-ai-act-mapping.md`, `docs/owasp-llm-top10-mapping.md`, `docs/iso-42001-mapping.md`, delete the existing hand-curated table (the `| ... | ... | ... |` block) and replace it with:

```
<!-- AUTOGEN:START -->
<!-- AUTOGEN:END -->
```

Leave every other line (title, **Source:** line, scope notes, the GPAI note, the ISO closing paragraph, etc.) untouched.

- [ ] **Step 6: Run the generator for real**

Run: `python tools/generate_artifacts.py`
Expected: no errors. Then inspect `docs/nist-ai-rmf-mapping.md` — confirm it now contains a row `| AIGOV-008 Transparency and model documentation | GOVERN 1.3; MAP 5.1 |` (this is the drift bug from the original review, now fixed because the table is generated straight from the CSV).

- [ ] **Step 7: Lint and full suite**

Run: `ruff check . && pytest --cov --cov-report=term-missing`
Expected: ruff clean; all tests pass.

- [ ] **Step 8: Commit**

```bash
git add tools/generate_artifacts.py tests/test_generate_artifacts.py docs/*.md
git commit -m "feat(tools): generate per-framework doc tables from the catalog, fix AIGOV-008/NIST drift"
```

---

### Task 6: Rego reads `data.json`, gets unit tests

**Files:**
- Modify: `controls/policies/governance.rego`
- Create: `controls/policies/governance_test.rego`
- Modify: `controls/policies/README.md`

**Interfaces:**
- Consumes: `controls/policies/data.json` (from Task 4) via OPA's automatic `data` loading for files under the policy path.
- Produces: `required_controls` (now `data.required_controls` instead of a literal set); `satisfied(id)`, `waived(id)`, `deny` rules unchanged in behavior.

- [ ] **Step 1: Modify `controls/policies/governance.rego`**

Replace lines 12–20 (the hardcoded set) with a reference to the generated data:

```rego
# Controls that must be enforced in code for any deployed LLM system.
# Generated into controls/policies/data.json by tools/generate_artifacts.py
# from the "Enforced in CI" column of controls/unified_controls.csv — do not
# hardcode IDs here, they will drift from the catalog.
required_controls := data.required_controls
```

The rest of the file (`satisfied`, `waived`, both `deny contains` rules) stays exactly as-is — they already reference `required_controls` by name, so this is a drop-in swap.

- [ ] **Step 2: Create `controls/policies/governance_test.rego`**

```rego
package main

import rego.v1

test_denies_missing_required_control if {
	deny["required control AIGOV-003 is not satisfied or waived"] with input as {"controls": {}}
		with data.required_controls as ["AIGOV-003"]
}

test_allows_satisfied_with_evidence if {
	count(deny) == 0 with input as {"controls": {"AIGOV-003": {"status": "satisfied", "evidence": "KMS"}}}
		with data.required_controls as ["AIGOV-003"]
}

test_denies_satisfied_without_evidence if {
	deny["control AIGOV-003 is marked satisfied but has no evidence"] with input as {"controls": {"AIGOV-003": {"status": "satisfied"}}}
		with data.required_controls as ["AIGOV-003"]
}

test_allows_waived_control if {
	count(deny) == 0 with input as {"controls": {"AIGOV-003": {"status": "not_applicable"}}}
		with data.required_controls as ["AIGOV-003"]
}
```

- [ ] **Step 3: Run the OPA test suite**

Run: `opa test controls/policies -v`
Expected: 4 tests, all `PASS`. (If `opa` isn't installed locally: `brew install opa`, or download the binary for your OS from the OPA project's releases and put it on `PATH` — CI installs it in Task 7, this local run is just to verify the policy before pushing.)

- [ ] **Step 4: Run conftest against the real example**

Run: `conftest test examples/sample_input.json -p controls/policies`
Expected: `4 tests, 4 passed, 0 warnings, 0 failures, 0 exceptions` (or similar conftest success summary) — confirms `governance.rego` correctly reads the real `controls/policies/data.json` produced in Task 4, not just the test fixtures.

- [ ] **Step 5: Update `controls/policies/README.md`**

Replace the body (keep the `# OPA / Rego policies` heading) with:

```markdown
Policy-as-code enforcement of the machine-checkable controls in
[`../unified_controls.csv`](../unified_controls.csv). Evaluated with
[conftest](https://www.conftest.dev) (which embeds Open Policy Agent).

## Run

```bash
python tools/generate_artifacts.py   # regenerates data.json from the CSV
conftest test examples/sample_input.json -p controls/policies
opa test controls/policies -v        # unit tests for the policy itself
```

`governance.rego` denies when a required control is neither `satisfied` nor
explicitly `not_applicable`, and when a `satisfied` control carries no
`evidence`. The required-control list isn't hardcoded here — it's
`data.required_controls`, generated from the `Enforced in CI` column of the
catalog CSV, so it can't drift from the catalog the way a hand-maintained
list could.

## Input shape

```json
{ "controls": { "AIGOV-003": { "status": "satisfied", "evidence": "KMS" } } }
```

This is wired into CI (`.github/workflows/ci.yml`) and blocks the build when
it fails.
```

- [ ] **Step 6: Commit**

```bash
git add controls/policies/governance.rego controls/policies/governance_test.rego controls/policies/README.md
git commit -m "feat(policy): read required controls from generated data.json, add opa test suite"
```

---

### Task 7: Wire it all into CI

**Files:**
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `tools/generate_artifacts.py` (Tasks 4–5), `controls/policies/governance_test.rego` (Task 6), `examples/sample_input.json` (existing).

- [ ] **Step 1: Replace `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Python deps
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Install OPA
        uses: open-policy-agent/setup-opa@v2
        with:
          version: latest
      - name: Install conftest
        run: |
          CONFTEST_VERSION=$(curl -s https://api.github.com/repos/open-policy-agent/conftest/releases/latest | grep '"tag_name"' | sed -E 's/.*"v([^"]+)".*/\1/')
          curl -sL "https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz" -o conftest.tar.gz
          tar xzf conftest.tar.gz conftest
          sudo mv conftest /usr/local/bin/
          conftest --version
      - name: Regenerate artifacts and check for drift
        run: |
          python tools/generate_artifacts.py
          git diff --exit-code -- controls/policies/data.json docs/*.md
      - name: OPA policy unit tests
        run: opa test controls/policies -v
      - name: Lint
        run: ruff check .
      - name: Test
        run: pytest --cov --cov-report=term-missing
      - name: Compliance gate (example)
        run: compliance-check examples/sample_project.yaml
      - name: Conftest policy gate (example)
        run: conftest test examples/sample_input.json -p controls/policies
```

(`Install conftest` discovers the latest release tag via the GitHub API rather than a hardcoded version — pin to a specific tag here later if build reproducibility becomes a concern.)

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: install opa/conftest, check generated artifacts for drift, run opa test and conftest test"
```

(This step can't be locally "run to verify it passes" the way a pytest step can — verification happens on the next push/PR. Tasks 1–6 already exercised every command this workflow runs, locally, with passing results.)

---

### Task 8: Docs — README and example catch up

**Files:**
- Modify: `README.md`
- Modify: `examples/sample_project.yaml`

**Interfaces:**
- None (documentation/example only — no code interfaces).

- [ ] **Step 1: Update the "Project config format" section in `README.md`**

After the existing bullet list (today's lines 105–107: the `status: satisfied` / `status: not_applicable` / "Omitted controls are gaps" bullets), add:

```markdown
- An optional top-level `risk_tier: high|limited|minimal` (default `high`)
  scopes which controls apply. A control whose catalog `Risk Tiers` doesn't
  include the project's tier is auto-waived when omitted — but an explicit
  `status:` declaration always wins over the auto-waiver, so you can still
  address a control by hand even outside your declared tier.
```

- [ ] **Step 2: Update the "Policy-as-code" section**

Replace the existing paragraph (today's lines 117–120, ending "...nor explicitly waived, or is satisfied without evidence. Wire it into CI to block deploys.") with:

```markdown
`governance.rego` denies when a required control (encryption, input/output
moderation, audit logging, access control, rate limiting) is neither
satisfied nor explicitly waived, or is satisfied without evidence. The
required-control list is generated from the catalog's `Enforced in CI`
column (`tools/generate_artifacts.py` → `controls/policies/data.json`), not
hardcoded — and it's wired into CI (`.github/workflows/ci.yml`) to block
the build on failure.
```

- [ ] **Step 3: Update the "Testing" section**

Replace today's fenced block (lines 145–148) with:

```bash
pytest --cov --cov-report=term-missing   # tests, 100% source coverage
ruff check .
python tools/generate_artifacts.py && git diff --exit-code   # generated artifacts must match the CSV
opa test controls/policies -v
compliance-check examples/sample_project.yaml   # the example must pass (exit 0)
conftest test examples/sample_input.json -p controls/policies
```

- [ ] **Step 4: Add `risk_tier` to the bundled example**

In `examples/sample_project.yaml`, after the `name:` line, add:

```yaml
risk_tier: high  # default; shown explicitly here since this is the reference example
```

- [ ] **Step 5: Verify the example still passes**

Run: `compliance-check examples/sample_project.yaml`
Expected: `satisfied: 15  waived: 1  gaps: 0` and exit code `0`, same as before — `risk_tier: high` changes nothing here since every control's default `risk_tiers` already includes `high`.

- [ ] **Step 6: Commit**

```bash
git add README.md examples/sample_project.yaml
git commit -m "docs: document risk_tier, generated artifacts, and the now-wired conftest/opa CI gates"
```

---

### Task 9: Full end-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Clean run of the entire pipeline**

```bash
python tools/generate_artifacts.py && git diff --exit-code
ruff check .
pytest --cov --cov-report=term-missing
opa test controls/policies -v
compliance-check examples/sample_project.yaml
conftest test examples/sample_input.json -p controls/policies
```

Expected: every command exits `0`; `pytest` coverage on `src/aigov/*` stays at 100%; `git diff --exit-code` after regenerating proves nothing in the repo is stale relative to the CSV (the core drift-prevention guarantee this whole plan exists for).

- [ ] **Step 2: Spot-check the four regenerated docs**

Confirm `docs/nist-ai-rmf-mapping.md` contains the AIGOV-008 row (the original drift bug) and that all four `docs/*-mapping.md` AUTOGEN blocks list every control whose framework citation isn't `—`.

- [ ] **Step 3: Final commit (if Step 1 produced any uncommitted changes)**

```bash
git status
```

If clean, nothing to do — every task above already committed its own changes. If anything is dirty (e.g. a regenerated artifact that drifted during this verification pass), stage and commit it with a message describing what was stale and why.
