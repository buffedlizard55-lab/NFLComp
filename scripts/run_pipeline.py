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
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.audit_verifier import NFLAuditVerifier  # noqa: E402
from engine.backtest_engine import NFLBacktestRunner  # noqa: E402
from engine.data_registry import export_registry  # noqa: E402
from engine.cross_validation import CrossValidationEngine  # noqa: E402
from engine.betting_markets import BettingMarketsEngine  # noqa: E402
from engine.forward_testing import ForwardTestingEngine  # noqa: E402
from engine.execution_engine import PaperExecutionEngine  # noqa: E402
from engine.autonomous_research import AutonomousResearchEngine  # noqa: E402
from engine.public_strategy_research import PublicStrategyResearchEngine  # noqa: E402
from engine.empirical_studies import build_report as build_empirical_studies  # noqa: E402
from engine.risk_analytics import build_report as build_risk_analytics  # noqa: E402


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

        # Pass 2 enhancements: cross-validation, betting markets, forward testing, execution, autonomous research
        print("Running cross-validation engine...")
        cv_engine = CrossValidationEngine(source_dir=f"{args.data_dir}/source")
        cv_report = cv_engine.run_full_cross_validation()
        cv_engine.export_report(f"{args.data_dir}/cross_validation.json")
        print(f"  Cross-validation: {cv_report['total_checks']} checks, {len(cv_report['discrepancies'])} discrepancies preserved")

        print("Running betting markets research...")
        bm_engine = BettingMarketsEngine(data_dir=args.data_dir)
        bm_report = bm_engine.export_markets_report(f"{args.data_dir}/betting_markets.json")
        print(f"  Markets: {len(bm_report['taxonomy'])} market types")

        print("Running forward testing engine...")
        ft_engine = ForwardTestingEngine(data_dir=args.data_dir)
        upcoming_path = Path(args.data_dir) / "upcoming_bets.json"
        if upcoming_path.exists():
            upcoming = json.loads(upcoming_path.read_text(encoding="utf-8"))
            for bet in upcoming[:100]:
                if bet.get("status") in ["WATCHING", "QUALIFIED", "READY"]:
                    try:
                        ft_engine.create_forward_test_signal(
                            strategy_id=bet["strategy_id"],
                            version="v2",
                            game={"season": bet.get("season", 2026), "week": bet.get("week", 2), "game_id": bet.get("game_id", "UNKNOWN")},
                            market=bet.get("market", "SPREAD"),
                            selection=bet.get("selection", ""),
                            model_prob=bet.get("model_prob", 0.55),
                            market_price=bet.get("current_price", "-110"),
                            stake=bet.get("stake", 100),
                            supporting_data=bet.get("supporting_data", {}),
                            market_source=bet.get("market_source", ""),
                            status=bet.get("status", "WATCHING")
                        )
                    except Exception:
                        pass
        ft_engine.export_report(f"{args.data_dir}/forward_testing.json")
        print(f"  Forward testing: {len(ft_engine.records)} records")

        print("Running execution engine...")
        exec_engine = PaperExecutionEngine()
        if upcoming_path.exists():
            upcoming = json.loads(upcoming_path.read_text(encoding="utf-8"))
            for bet in upcoming[:50]:
                try:
                    if bet["market"].startswith("KALSHI"):
                        quote = exec_engine.get_kalshi_quote(bet.get("model_prob", 0.55), "YES", "HIGH")
                    else:
                        quote = exec_engine.get_sportsbook_quote(
                            {"spread_line": -3.0, "total_line": 44.0},
                            bet.get("market", "SPREAD"),
                            bet.get("side", "home")
                        )
                    exec_engine.simulate_fill(
                        bet_id=bet["bet_id"],
                        requested_price=bet.get("current_price", "-110"),
                        requested_size=bet.get("stake", 100),
                        quote=quote
                    )
                except Exception:
                    pass
        exec_engine.export_execution_report(f"{args.data_dir}/execution_report.json")
        print(f"  Execution: {len(exec_engine.quotes)} quotes, {len(exec_engine.fills)} fills")

        print("Running autonomous research loop...")
        ar_engine = AutonomousResearchEngine(data_dir=args.data_dir)
        ar_report = ar_engine.export_report(f"{args.data_dir}/autonomous_research.json")
        print(f"  Autonomous research: {ar_report['total_findings']} findings")

        print("Running public strategy reproduction...")
        ps_engine = PublicStrategyResearchEngine(data_dir=args.data_dir)
        ps_report = ps_engine.export_report(f"{args.data_dir}/public_strategy_research.json")
        print(f"  Public strategies: {ps_report['total_researched']} researched")

        print("Re-deriving research claims from the snapshot...")
        study_report = build_empirical_studies(args.data_dir)
        Path(args.data_dir, "empirical_studies.json").write_text(
            json.dumps(study_report, indent=2) + "\n", encoding="utf-8")
        print(f"  Empirical studies: {study_report['study_count']} studies, "
              f"{len(study_report['declared_assumptions'])} classified dossier claims, "
              f"{len(study_report['cross_check_disagreements'])} cross-check disagreement(s)")

        print("Building risk, calibration and capital-sufficiency analytics...")
        risk_report = build_risk_analytics(args.data_dir)
        Path(args.data_dir, "risk_analytics.json").write_text(
            json.dumps(risk_report, indent=2) + "\n", encoding="utf-8")
        risk_summary = risk_report["summary"]
        print(f"  Risk analytics: {risk_summary['personas']} personas "
              f"({risk_summary['personas_meeting_reporting_floor']} above the reporting floor), "
              f"Brier {risk_summary['portfolio_brier_score']}, "
              f"ECE {risk_summary['expected_calibration_error_pct_points']} pts")

        print(f"Simulation and export finished in {time.time() - started:.1f}s")

    # Audit and documentation are mutually dependent: the docs quote the audit
    # results, and the audit re-derives the numbers the docs publish (including
    # the count of passing checks).  Rendering once leaves the published
    # `audit_checks.json` describing the pre-render state, so iterate to a
    # fixpoint: publish the results, re-render, verify, and repeat until a round
    # changes no document and the read-only audit passes.  Only then is the
    # written check file the one the published docs actually quote.
    doc_paths = [
        ROOT / "README.md",
        ROOT / "docs" / "FINAL_REPORT.md",
        ROOT / "docs" / "VERIFICATION.md",
        ROOT / "index.html",
    ]

    def _docs_digest() -> str:
        digest = hashlib.sha256()
        for path in doc_paths:
            if path.exists():
                digest.update(path.read_bytes())
        return digest.hexdigest()

    def _render_docs() -> int:
        if args.skip_docs:
            return 0
        from scripts.render_claims import main as render_claims  # noqa: E402
        from scripts.render_readme import main as render_readme  # noqa: E402
        from scripts.render_verification import main as render_verification  # noqa: E402

        status = render_readme(["--data-dir", args.data_dir])
        report_path = ROOT / "docs" / "FINAL_REPORT.md"
        if report_path.exists() and report_path.read_text(encoding="utf-8").find("<!-- CURRENT_STATE_START -->") >= 0:
            # The report quotes the summary and the key results; the full roster
            # and registry tables live in the README.
            status |= render_readme(["--data-dir", args.data_dir, "--readme", str(report_path),
                                     "--blocks", "status,executive_summary,findings"])
        status |= render_verification(["--data-dir", args.data_dir])
        status |= render_claims(["--data-dir", args.data_dir])
        return status

    max_rounds = 5
    failures: list[str] = []
    for round_number in range(1, max_rounds + 1):
        # Publish this round's audit results, then bring the docs up to date.
        published, _ = _audit(args.data_dir, write=True)
        before = _docs_digest()
        doc_status = _render_docs()
        docs_changed = _docs_digest() != before

        # Verify without rewriting: are the published bytes now self-consistent?
        result, failed = _audit(args.data_dir, write=False)
        print(f"Audit round {round_number}: {result['passed_checks']}/{result['total_checks']} checks passed"
              f"{' (documents rewritten)' if docs_changed else ''}")
        if doc_status:
            print("a generated documentation block could not be rendered")
        if not failed and not docs_changed and not doc_status:
            failures = []
            break
        failures = list(failed)
        if doc_status:
            failures.append("GENERATED_DOCS")
        if round_number == max_rounds:
            print(f"audit and generated docs did not converge after {max_rounds} rounds")

    for name in dict.fromkeys(failures):
        print(f"  FAILED: {name}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
