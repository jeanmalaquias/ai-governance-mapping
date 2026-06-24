# Catalog Schema v2: generated artifacts, catalog versioning, risk tiers

**Date:** 2026-06-24
**Status:** Approved design, pending implementation plan.

## Problem

A repo critique surfaced four related gaps, all rooted in the catalog
(`controls/unified_controls.csv`) not being the actual single source of
truth it claims to be:

1. **Docs ↔ catalog drift.** `docs/nist-ai-rmf-mapping.md` is missing a row
   for AIGOV-008 even though the CSV's NIST column (`GOVERN 1.3; MAP 5.1`)
   says it should map there. Nothing catches this kind of drift.
2. **Duplicated control list.** `controls/policies/governance.rego` hardcodes
   a `required_controls` set (6 IDs) that is supposed to mirror a subset of
   the CSV. Add a control to the CSV, forget Rego, the gate silently doesn't
   cover it.
3. **No catalog version in output.** `compliance-check`'s gap report doesn't
   say which revision of the catalog graded the project. Frameworks amend;
   an old report becomes unverifiable evidence.
4. **No risk-tier concept.** Every project must individually waive (with a
   hand-written reason) every catalog control that doesn't apply to it. EU AI
   Act obligations actually vary by risk classification (high-risk gets the
   full Title III obligations; limited-risk gets transparency-only; minimal
   gets none) — the catalog doesn't represent that.

## Design

### 1. Catalog schema additions

Two new columns on `controls/unified_controls.csv`, plus one new file:

- **`Enforced in CI`** — `yes` / `no`. Marks the security-floor subset that
  must be gated by `governance.rego` regardless of EU AI Act risk
  classification. This is exactly today's hardcoded 6:
  AIGOV-003, AIGOV-006, AIGOV-007, AIGOV-009, AIGOV-010, AIGOV-015.

- **`Risk Tiers`** — semicolon-separated subset of `high;limited;minimal`.
  Which EU AI Act risk tiers a control applies to. Every `Enforced in CI =
  yes` control gets all three tiers (security hygiene isn't conditioned on
  legal risk classification — confirmed in design discussion). Proposed
  default values for the other rows, derived from each row's existing `EU AI
  Act` column citation (Title III high-risk-specific articles → `high` only;
  GDPR-grounded controls → all three, since GDPR applies independent of AI
  Act tier):

  | ID | Enforced in CI | Risk Tiers | Basis |
  |----|----|----|----|
  | AIGOV-001 | no | high | Art. 9 is Title III high-risk-only |
  | AIGOV-002 | no | high | Art. 10 is Title III high-risk-only |
  | AIGOV-003 | yes | high;limited;minimal | security floor |
  | AIGOV-004 | no | high;limited;minimal | GDPR Art. 5(1)(e) is universal |
  | AIGOV-005 | no | high | Art. 14 is Title III high-risk-only |
  | AIGOV-006 | yes | high;limited;minimal | security floor |
  | AIGOV-007 | yes | high;limited;minimal | security floor |
  | AIGOV-008 | no | high | Art. 11/13 are Title III high-risk-only |
  | AIGOV-009 | yes | high;limited;minimal | security floor |
  | AIGOV-010 | yes | high;limited;minimal | security floor |
  | AIGOV-011 | no | high | Art. 72 post-market monitoring is high-risk-only |
  | AIGOV-012 | no | high | Art. 72/73 are Title III high-risk-only |
  | AIGOV-013 | no | high | Art. 25 value-chain obligation is high-risk-only |
  | AIGOV-014 | no | high;limited;minimal | GDPR Arts. 5/25 are universal |
  | AIGOV-015 | yes | high;limited;minimal | security floor |
  | AIGOV-016 | no | high | Art. 10(2)(f) bias examination is high-risk-only |

  This is an interpretive default (consistent with the repo's existing "not
  legal advice" disclaimer), not a legal determination — a project can
  always override by explicitly declaring a control's status in its own
  YAML, which beats the tier-derived auto-waiver (see §3).

- **`controls/CATALOG_VERSION`** — plain semver string (starts at `1.1.0`
  for this change), bumped by hand whenever the CSV changes. A separate
  file rather than a CSV pseudo-row, so `csv.DictReader` parsing stays
  simple.

### 2. Generator script

New `tools/generate_artifacts.py`, run in CI before lint/test:

- Reads the CSV + `CATALOG_VERSION`.
- Writes `controls/policies/data.json`:
  ```json
  { "required_controls": ["AIGOV-003", "AIGOV-006", "..."], "catalog_version": "1.1.0" }
  ```
  built from rows where `Enforced in CI = yes`.
- Regenerates the mapping-table block inside each `docs/*-mapping.md`,
  between `<!-- AUTOGEN:START -->` / `<!-- AUTOGEN:END -->` markers, so
  hand-written prose around the table survives regeneration.
- `governance.rego` drops its hardcoded `required_controls` set and reads
  `data.required_controls` instead (standard OPA/conftest external-data
  pattern — conftest auto-loads `data.json` files found under the policy
  path).

CI gets a new step: run the generator, then `git diff --exit-code`. Fails
the build if the committed docs or `data.json` are stale relative to the
CSV — this is what actually prevents both gap #1 (drift) and gap #2
(duplication) from recurring, not just fixes today's instance.

### 3. `check.py` / CLI changes

- `Control` (in `catalog.py`) gains `enforced_in_ci: bool` and
  `risk_tiers: list[str]`, parsed from the two new CSV columns.
- Project YAML gains an optional top-level `risk_tier: high|limited|minimal`.
  **Default is `high`** when omitted — an unset tier assumes the strictest
  reading and auto-waives nothing, so existing project YAMLs (like
  `examples/sample_project.yaml`) keep behaving exactly as today unless they
  opt in to a lower tier.
- `_classify()` logic: if the control is **not** explicitly declared in the
  project's `controls:` map, and `project_tier not in control.risk_tiers`,
  return `("waived", f"not applicable at risk_tier={tier} (catalog v{version})")`
  automatically. An explicit declaration in the YAML — `satisfied` or
  `not_applicable` with its own reason — always wins over the tier-derived
  auto-waiver; tier only fills in for controls the author didn't address.
- `GapReport` gains `catalog_version: str`, populated from
  `CATALOG_VERSION`, rendered in the CLI's report header.

### 4. Testing

- `tests/test_aigov.py`: tier auto-waiver fires for an undeclared
  high-only control when `risk_tier: minimal`; an explicit YAML declaration
  overrides the auto-waiver even at a non-matching tier; `catalog_version`
  shows up in `GapReport` and the rendered output.
- New `tests/test_generate_artifacts.py`: generator produces correct
  `data.json` from a small fixture CSV; doc-marker regeneration leaves
  surrounding prose untouched.
- New `controls/policies/governance_test.rego` (`opa test`): required-set
  assertions driven by a fixture `data.json`, not a hardcoded list.
- CI additions: `python tools/generate_artifacts.py && git diff --exit-code`,
  `opa test controls/policies`, and
  `conftest test examples/sample_input.json -p controls/policies`. The
  conftest step also resolves the earlier "policy-as-code claimed but never
  run in CI" finding, since it's now backed by generated, tested data.

## Out of scope

- Renegotiating which EU AI Act articles are "Title III high-risk-only" vs
  universal beyond the table in §1 — that's a one-time data migration, not
  an ongoing design question. Future catalog edits set `Risk Tiers` per-row
  as part of normal review.
- Evidence verification / artifact existence checking (raised in the
  original critique as a separate, larger concern) — not addressed here.
- The `unacceptable`-risk EU AI Act tier — out of scope by definition: a
  system in that tier is banned, not something this tool gates.
