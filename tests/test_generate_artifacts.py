import json
import sys
from pathlib import Path

import pytest

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


def test_committed_data_json_matches_real_csv():
    """The committed controls/policies/data.json must match what regenerating
    from the real controls/unified_controls.csv currently produces. This is
    also enforced in CI via `generate_artifacts.py` + `git diff --exit-code`,
    but we want the guarantee checked by the test suite too. Read-only: must
    not write to DATA_JSON_PATH.
    """
    rows = ga.load_rows()
    version = ga.VERSION_PATH.read_text(encoding="utf-8").strip()
    expected = ga.build_data_json(rows, version)

    committed = json.loads(ga.DATA_JSON_PATH.read_text(encoding="utf-8"))

    assert committed == expected


def test_update_doc_raises_without_markers(tmp_path, monkeypatch):
    doc_path = tmp_path / "docs"
    doc_path.mkdir()
    target = doc_path / "no-markers.md"
    target.write_text("# Title\n\nNo markers here.\n", encoding="utf-8")
    monkeypatch.setattr(ga, "DOCS_DIR", doc_path)

    with pytest.raises(SystemExit):
        ga.update_doc("no-markers.md", "EU AI Act", [])
