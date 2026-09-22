#!/usr/bin/env python3
"""One-command reproduction of every published NFLComp artifact.

The research loop is: load verified sources -> walk-forward backtest and paper
trade -> export the derived data layer -> regenerate the docs that quote it ->
verify the published claims.  This script performs that loop end to end, in
order, and fails loudly if any step does not reconcile.

Usage::

    python3 scripts/run_pipeline.py                 # full run + docs + audit
    python3 scripts/run_pipeline.py --skip-docs     # data only
    python3 scripts/run_pipeline.py --check-only    # re-verify, do not simulate

Nothing here places a real bet: the runner only simulates paper wagers against
prices recorded in the source snapshots.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_verifier import NFLAuditVerifier  # noqa: E402
from engine.backtest_engine import NFLBacktestRunner  # noqa: E402
from engine.data_registry import export_registry  # noqa: E402


def _audit(data_dir: str, write: bool) -> tuple[dict, list[str]]:
    verifier = NFLAuditVerifier(data_dir)
    result = verifier.run_full_audit(write=write)
    failed = [check["name"] for check in verifier.audit_checks if not check["passed"]]
    return result, failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(ROOT / "data"))
    parser.add_argument("--skip-docs", action="store_true")
    parser.add_argument("--check-only", action="store_true",
                        help="skip the simulation and only re-verify the published files")
    args = parser.parse_args(argv)

    if not args.check_only:
        started = time.time()
        runner = NFLBacktestRunner()
        runner.run_simulation()
        runner.generate_research_experiments()
        runner.export_all_data(args.data_dir)
        export_registry(args.data_dir)
        print(f"Simulation and export finished in {time.time() - started:.1f}s")

    # Pass 1: produce the audit results the docs quote.
    first_result, first_failed = _audit(args.data_dir, write=True)
    print(f"Audit pass 1: {first_result['passed_checks']}/{first_result['total_checks']} checks passed")

    doc_status = 0
    if not args.skip_docs:
        from scripts.render_claims import main as render_claims  # noqa: E402
        from scripts.render_readme import main as render_readme  # noqa: E402
        from scripts.render_verification import main as render_verification  # noqa: E402

        doc_status = render_readme(["--data-dir", args.data_dir])
        report_path = ROOT / "docs" / "FINAL_REPORT.md"
        if report_path.exists() and report_path.read_text(encoding="utf-8").find("<!-- CURRENT_STATE_START -->") >= 0:
            doc_status |= render_readme(["--data-dir", args.data_dir, "--readme", str(report_path)])
        doc_status |= render_verification(["--data-dir", args.data_dir])
        doc_status |= render_claims(["--data-dir", args.data_dir])
        if doc_status:
            print("a generated documentation block could not be rendered")

    # Pass 2: verify the artifacts exactly as they now stand, without rewriting.
    result, failed = _audit(args.data_dir, write=False)
    print(f"Audit pass 2 (published artifacts): {result['passed_checks']}/{result['total_checks']} checks passed")

    failures = list(failed)
    if doc_status:
        failures.append("GENERATED_DOCS")
    for name in failures:
        print(f"  FAILED: {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
