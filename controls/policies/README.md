# OPA / Rego policies

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
