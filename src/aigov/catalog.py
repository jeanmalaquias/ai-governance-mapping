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
