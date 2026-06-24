import pytest

from aigov import cli
from aigov.catalog import Control, load_catalog
from aigov.check import ControlResult, GapReport, evaluate, load_project


def test_catalog_loads_all_controls():
    controls = load_catalog()
    ids = [c.id for c in controls]
    assert "AIGOV-001" in ids
    assert "AIGOV-016" in ids
    assert len(controls) == 16
    assert all(c.control for c in controls)


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


def test_load_catalog_skips_blank_id_rows(tmp_path):
    csv_path = tmp_path / "with_blank_id.csv"
    csv_path.write_text(
        "ID,Control\nAIGOV-001,Risk assessment\n,Empty ID control\n",
        encoding="utf-8",
    )
    controls = load_catalog(csv_path)
    assert len(controls) == 1
    assert controls[0].id == "AIGOV-001"
    assert controls[0].control == "Risk assessment"


def _catalog():
    return [
        Control(id="AIGOV-001", control="Risk assessment"),
        Control(id="AIGOV-003", control="Encryption at rest"),
        Control(id="AIGOV-009", control="Audit logging"),
        Control(id="AIGOV-016", control="Bias testing"),
    ]


def test_evaluate_classifies_every_state():
    project = {
        "name": "Svc",
        "controls": {
            "AIGOV-001": {"status": "satisfied", "evidence": "risk.md"},
            "AIGOV-003": {"status": "satisfied"},  # no evidence -> gap
            "AIGOV-016": {"status": "not_applicable", "reason": "informational only"},
            # AIGOV-009 omitted entirely -> gap
        },
    }
    report = evaluate(project, _catalog())
    by_id = {r.id: r for r in report.results}
    assert by_id["AIGOV-001"].state == "satisfied"
    assert by_id["AIGOV-003"].state == "gap"
    assert by_id["AIGOV-016"].state == "waived"
    assert by_id["AIGOV-009"].state == "gap"
    assert report.has_gaps
    assert report.counts() == {"satisfied": 1, "waived": 1, "gap": 2}


def test_evaluate_flags_bad_status_and_missing_reason():
    catalog = [
        Control(id="AIGOV-001", control="A"),
        Control(id="AIGOV-003", control="B"),
    ]
    project = {
        "controls": {
            "AIGOV-001": {"status": "in_progress"},  # unrecognized
            "AIGOV-003": {"status": "not_applicable"},  # missing reason
        }
    }
    report = evaluate(project, catalog)
    assert report.project == "unnamed"
    assert all(r.state == "gap" for r in report.results)


def test_cli_passes_on_complete_example():
    assert cli.main(["examples/sample_project.yaml"]) == 0


_SATISFIED = (
    "name: P\ncontrols:\n  AIGOV-001:\n    status: satisfied\n    evidence: x\n"
)


def test_cli_fails_on_gaps(tmp_path):
    p = tmp_path / "proj.yaml"
    p.write_text(_SATISFIED)
    # Only one control declared; the rest of the catalog is unaddressed → gaps.
    assert cli.main([str(p)]) == 1


def test_cli_accepts_catalog_override(tmp_path):
    catalog = tmp_path / "cat.csv"
    catalog.write_text("ID,Control\nAIGOV-001,Risk assessment\n")
    proj = tmp_path / "proj.yaml"
    proj.write_text(_SATISFIED)
    assert cli.main([str(proj), "--catalog", str(catalog)]) == 0


def test_load_project_empty(tmp_path):
    p = tmp_path / "empty.yaml"
    p.write_text("")
    assert load_project(p) == {}


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
    # high is in scope by default, undeclared -> gap
    assert report.results[0].state == "gap"


def test_evaluate_rejects_unknown_risk_tier():
    catalog = [Control(id="AIGOV-001", control="Risk assessment", risk_tiers=["high"])]
    project = {"risk_tier": "bogus", "controls": {}}
    with pytest.raises(ValueError):
        evaluate(project, catalog)


def test_cli_exits_2_on_unknown_risk_tier(tmp_path):
    p = tmp_path / "bad_tier.yaml"
    p.write_text("name: Bad\nrisk_tier: hgih\ncontrols: {}\n")
    assert cli.main([str(p)]) == 2


def test_render_shows_catalog_version():
    result = ControlResult(
        id="AIGOV-001", control="X", state="satisfied", detail="d"
    )
    report = GapReport(
        project="P",
        results=[result],
        catalog_version="1.1.0",
    )
    output = cli.render(report)
    assert "catalog version: 1.1.0" in output
