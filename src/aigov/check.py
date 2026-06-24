"""Evaluate a project's declared controls against the catalog → gap report."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from .catalog import Control, load_catalog, load_catalog_version

VALID_RISK_TIERS = {"high", "limited", "minimal"}


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
    if project_tier not in VALID_RISK_TIERS:
        raise ValueError(
            f"unknown risk_tier '{project_tier}'; expected one of "
            f"{sorted(VALID_RISK_TIERS)}"
        )
    results: list[ControlResult] = []
    for control in controls:
        state, detail = _classify(
            declared.get(control.id), control, project_tier, version
        )
        results.append(
            ControlResult(
                id=control.id, control=control.control, state=state, detail=detail
            )
        )
    return GapReport(
        project=project.get("name", "unnamed"), results=results, catalog_version=version
    )
