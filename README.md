# AI Governance Mapping

> One **unified controls catalog** crosswalking four AI governance frameworks —
> **NIST AI RMF 1.0** (+ Generative AI Profile), the **EU AI Act**, the **OWASP
> LLM Top 10 (2025)**, and **ISO/IEC 42001:2023** — plus Open Policy Agent
> policies, documentation templates, and a CLI that produces a compliance **gap
> report** for a project.

<!-- Badges placeholder: CI · license -->

---

## Contents

- [Why this exists](#why-this-exists)
- [What's inside](#whats-inside)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Project config format](#project-config-format)
- [Policy-as-code (OPA / conftest)](#policy-as-code-opa--conftest)
- [Frameworks covered](#frameworks-covered)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Scope & disclaimer](#scope--disclaimer)

## Why this exists

Enterprise AI teams comply with several frameworks at once, and the controls
overlap heavily. Four separate checklists is wasteful and drifts out of sync.
This repo collapses them into **one catalog of controls**, each mapped back to
every framework with implementation guidance, tooling, and the evidence an
auditor expects — then gives you code to check a project against it.

The catalog itself is the artifact:
[`controls/unified_controls.csv`](controls/unified_controls.csv) (16 controls × 9 columns).

> **Runtime companion:** this repo is the *paperwork*. The
> [AI Governance Toolkit](https://github.com/jeanmalaquias/ai-governance-toolkit)
> is the *code that enforces and evidences* these controls at runtime.

## What's inside

| Path | What |
|------|------|
| [`controls/unified_controls.csv`](controls/unified_controls.csv) | Master crosswalk — one control per row, mapped to all four frameworks |
| [`docs/`](docs/) | Per-framework explainers crosswalking back to control IDs, with source citations |
| [`controls/policies/`](controls/policies/) | OPA (Rego) policies enforcing the machine-checkable controls |
| [`templates/`](templates/) | Model card, risk assessment, and audit-log schema templates |
| [`src/aigov/`](src/aigov/) + [`tools/compliance_check.py`](tools/compliance_check.py) | The `compliance-check` CLI |
| [`articles/`](articles/) | Deep-dive article drafts (generic methodology) |

## Prerequisites

- **Python 3.12+** for the CLI.
- Optional: [**conftest**](https://www.conftest.dev) (embeds Open Policy Agent)
  to run the Rego policies.

## Installation

```bash
git clone https://github.com/jeanmalaquias/ai-governance-mapping.git
cd ai-governance-mapping
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

Check a project's declared controls against the catalog:

```bash
compliance-check examples/sample_project.yaml
```

Expected output (the bundled example satisfies/waives every control):

```
# Compliance gap report — Sample RAG Service

satisfied: 15  waived: 1  gaps: 0

| control | state | detail |
| --- | --- | --- |
| AIGOV-001 AI risk assessment before deployment | satisfied | docs/risk_assessment-2026-06.md |
| ...
No gaps. All applicable controls satisfied or waived.
```

The command exits `0` when every control is satisfied or waived, `1` when gaps
remain, and `2` for an invalid project config (e.g. an unrecognized
`risk_tier`) — so it drops into CI as a gate, and a config error is
distinguishable from a real compliance gap.
Point it at your own project file, or override the catalog with `--catalog`.

## Project config format

A project declares how it addresses each control (YAML):

```yaml
name: My Service
controls:
  AIGOV-003: { status: satisfied, evidence: "AWS KMS envelope encryption" }
  AIGOV-016: { status: not_applicable, reason: "no decisions about individuals" }
  # any catalog control you omit is reported as a gap
```

- `status: satisfied` **requires** an `evidence` string, else it's a gap.
- `status: not_applicable` **requires** a `reason`, else it's a gap.
- Omitted controls are gaps ("not addressed").
- An optional top-level `risk_tier: high|limited|minimal` (default `high`)
  scopes which controls apply. A control whose catalog `Risk Tiers` doesn't
  include the project's tier is auto-waived when omitted — but an explicit
  `status:` declaration always wins over the auto-waiver, so you can still
  address a control by hand even outside your declared tier.

## Policy-as-code (OPA / conftest)

The machine-checkable controls are enforced as Rego:

```bash
conftest test examples/sample_input.json -p controls/policies
```

`governance.rego` denies when a required control (encryption, input/output
moderation, audit logging, access control, rate limiting) is neither satisfied
nor explicitly waived, or is satisfied without evidence. The required-control
list is generated from the catalog's `Enforced in CI` column
(`tools/generate_artifacts.py` → `controls/policies/data.json`), not
hardcoded — and it's wired into CI (`.github/workflows/ci.yml`) to block
the build on failure.

## Frameworks covered

- **NIST AI RMF 1.0** (Jan 2023) + **Generative AI Profile** (NIST-AI-600-1).
- **EU AI Act** — Regulation (EU) 2024/1689, high-risk obligations (Arts. 9–15, 72).
- **OWASP Top 10 for LLM Applications (2025)** — LLM01–LLM10.
- **ISO/IEC 42001:2023** — AI management system, Annex A controls.

## Project layout

```
controls/
├── unified_controls.csv     # the master crosswalk
└── policies/governance.rego # OPA policy-as-code
docs/                        # per-framework crosswalk explainers (cited)
templates/                   # model_card.md, risk_assessment.md, audit_log_schema.json
src/aigov/                   # catalog loader + gap-check engine + CLI
tools/compliance_check.py    # thin entry point (= compliance-check)
examples/                    # sample_project.yaml + sample_input.json
articles/                    # deep-dive drafts
```

## Testing

```bash
pytest --cov --cov-report=term-missing   # tests, 100% source coverage
ruff check .
python tools/generate_artifacts.py && git diff --exit-code   # generated artifacts must match the CSV
opa test controls/policies -v
compliance-check examples/sample_project.yaml   # the example must pass (exit 0)
conftest test examples/sample_input.json -p controls/policies
```

## Scope & disclaimer

Mappings are **interpretive aids, not legal advice**. Every framework reference
in [`docs/`](docs/) links to its primary source; classify your own system and
verify obligations against the regulations before relying on them.

## License

MIT (see [LICENSE](LICENSE)).
