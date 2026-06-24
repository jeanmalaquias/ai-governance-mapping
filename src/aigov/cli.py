"""compliance-check CLI: gap report for a project against the catalog."""

from __future__ import annotations

import argparse
import sys

from .check import GapReport, evaluate, load_project


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compliance-check")
    parser.add_argument("project", help="Path to the project YAML config.")
    parser.add_argument("--catalog", help="Override the unified controls CSV path.")
    args = parser.parse_args(argv)

    project = load_project(args.project)
    from .catalog import load_catalog

    catalog = load_catalog(args.catalog) if args.catalog else None
    try:
        report = evaluate(project, catalog)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    print(render(report))
    if report.has_gaps:
        print(f"\n{len(report.gaps)} gap(s) remain.")
        return 1
    print("\nNo gaps. All applicable controls satisfied or waived.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
