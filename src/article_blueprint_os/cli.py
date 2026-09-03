from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .backfill import export_coverage_report, run_historical_backfill
from .config import load_journals, load_screening_rules
from .db import connect, init_db
from .pipeline import enumerate_journal
from .pubmed import PubMedClient
from .review import create_calibration_sample, export_calibration_queue, export_llm_queue, import_llm_results, sample_no_audit
from .manual_web import prepare_web_batches, validate_web_output
from .screening import screen_database


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JOURNALS = REPO_ROOT / "config" / "journals.json"
DEFAULT_RULES = REPO_ROOT / "config" / "screening_rules.json"


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _open_db(path: str):
    connection = connect(path)
    init_db(connection)
    return connection


def command_init_db(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    connection.close()
    _print_json({"database": str(Path(args.db).expanduser().resolve()), "status": "initialized"})


def command_enumerate(args: argparse.Namespace) -> None:
    registry = load_journals(args.journals)
    selected = registry.journals if args.journal == "all" else (registry.by_key(args.journal),)
    client = PubMedClient(
        email=args.email,
        api_key=os.environ.get(args.api_key_env) if args.api_key_env else None,
    )
    connection = _open_db(args.db)
    results = []
    try:
        for journal in selected:
            results.append(
                enumerate_journal(
                    connection,
                    client,
                    registry,
                    journal,
                    start_date=args.start,
                    end_date=args.end,
                    batch_size=args.batch_size,
                    raw_dir=args.raw_dir,
                    progress=lambda message: print(message, file=sys.stderr, flush=True),
                )
            )
    finally:
        connection.close()
    _print_json({"runs": results})


def command_validate_registry(args: argparse.Namespace) -> None:
    registry = load_journals(args.journals)
    selected = registry.journals if args.journal == "all" else (registry.by_key(args.journal),)
    client = PubMedClient(
        email=args.email,
        api_key=os.environ.get(args.api_key_env) if args.api_key_env else None,
    )
    rows = []
    for journal in selected:
        from .pipeline import build_query

        query = build_query(journal, args.start, args.end)
        history = client.search_history(query)
        rows.append(
            {
                "key": journal.key,
                "title": journal.title,
                "pubmed_title": journal.pubmed_title,
                "tier": journal.tier,
                "count": history.count,
                "valid": history.count > 0,
            }
        )
        print(f"{journal.key}: {history.count}", file=sys.stderr, flush=True)
    _print_json(
        {
            "start": args.start,
            "end": args.end,
            "journal_count": len(rows),
            "zero_hit_count": sum(row["count"] == 0 for row in rows),
            "journals": rows,
        }
    )


def command_screen(args: argparse.Namespace) -> None:
    rules = load_screening_rules(args.rules)
    connection = _open_db(args.db)
    try:
        result = screen_database(connection, rules)
    finally:
        connection.close()
    _print_json({"rules_version": rules.version, **result})


def command_export_llm(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        count = export_llm_queue(connection, args.out)
    finally:
        connection.close()
    _print_json({"rows": count, "output": str(Path(args.out).expanduser().resolve())})


def command_create_calibration(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        result = create_calibration_sample(connection, seed=args.seed, prompt_version=args.prompt_version)
    finally:
        connection.close()
    _print_json(result)


def command_export_calibration(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        count = export_calibration_queue(connection, args.calibration_id, args.out)
    finally:
        connection.close()
    _print_json({"calibration_id": args.calibration_id, "rows": count, "output": str(Path(args.out).expanduser().resolve())})


def command_prepare_web_batches(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        result = prepare_web_batches(
            connection,
            args.calibration_id,
            args.out,
            batch_size=args.batch_size,
            software_revision=args.software_revision,
        )
    finally:
        connection.close()
    _print_json({"batches": len(result), "batch_ids": [x["batch_id"] for x in result]})


def command_validate_web_batch(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        records = validate_web_output(
            connection,
            args.manifest,
            args.output,
            model_display_name=args.model_display_name,
            operator=args.operator,
            fresh_chat_confirmed=args.fresh_chat_confirmed,
            executed_at=args.executed_at,
            attempt=args.attempt,
            execution_mode=args.execution_mode,
        )
    finally:
        connection.close()
    _print_json(
        {
            "validated": len(records),
            "manifest": str(Path(args.manifest).expanduser().resolve()),
            "attempt": args.attempt,
        }
    )


def command_import_llm(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        count = import_llm_results(connection, args.input)
    finally:
        connection.close()
    _print_json({"imported": count})


def command_sample_audit(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        result = sample_no_audit(connection, fraction=args.fraction, seed=args.seed)
    finally:
        connection.close()
    _print_json(result)


def command_status(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        payload = {
            "articles": connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "completed_enumeration_runs": connection.execute(
                "SELECT COUNT(*) FROM enumeration_runs WHERE status='complete'"
            ).fetchone()[0],
            "failed_enumeration_runs": connection.execute(
                "SELECT COUNT(*) FROM enumeration_runs WHERE status='failed'"
            ).fetchone()[0],
            "deterministically_screened": connection.execute(
                "SELECT COUNT(DISTINCT pmid) FROM deterministic_screens"
            ).fetchone()[0],
            "llm_screened": connection.execute(
                "SELECT COUNT(DISTINCT pmid) FROM llm_screens"
            ).fetchone()[0],
            "human_reviewed": connection.execute(
                "SELECT COUNT(DISTINCT pmid) FROM human_reviews"
            ).fetchone()[0],
            "historical_backfills": connection.execute(
                "SELECT COUNT(*) FROM historical_backfills"
            ).fetchone()[0],
        }
    finally:
        connection.close()
    _print_json(payload)


def command_historical_backfill(args: argparse.Namespace) -> None:
    registry = load_journals(args.journals)
    client = PubMedClient(
        email=args.email,
        api_key=os.environ.get(args.api_key_env) if args.api_key_env else None,
    )
    connection = _open_db(args.db)
    try:
        result = run_historical_backfill(
            connection,
            client,
            registry,
            start_date=args.start,
            end_date=args.end,
            raw_dir=args.raw_dir,
            batch_size=args.batch_size,
            software_revision=args.software_revision,
            resume_id=args.resume_id,
            progress=lambda message: print(message, file=sys.stderr, flush=True),
        )
        if args.report:
            export_coverage_report(connection, str(result["backfill_id"]), args.report)
            result["coverage_report"] = str(Path(args.report).expanduser().resolve())
    finally:
        connection.close()
    _print_json(result)


def command_coverage_report(args: argparse.Namespace) -> None:
    connection = _open_db(args.db)
    try:
        result = export_coverage_report(connection, args.backfill_id, args.out)
    finally:
        connection.close()
    _print_json(
        {
            "backfill_id": result["backfill_id"],
            "output": str(Path(args.out).expanduser().resolve()),
            "annual_checks": result["annual_checks"],
            "annual_discrepancies": result["annual_discrepancies"],
        }
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="article-blueprint")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="initialize the SQLite metadata database")
    init_parser.add_argument("--db", required=True)
    init_parser.set_defaults(func=command_init_db)

    enum_parser = subparsers.add_parser("enumerate", help="enumerate PubMed journal/date universes")
    enum_parser.add_argument("--db", required=True)
    enum_parser.add_argument("--journals", default=str(DEFAULT_JOURNALS))
    enum_parser.add_argument("--journal", default="all", help="registry key or 'all'")
    enum_parser.add_argument("--start", required=True)
    enum_parser.add_argument("--end", required=True)
    enum_parser.add_argument("--email", required=True, help="contact email sent to NCBI")
    enum_parser.add_argument("--api-key-env", default="NCBI_API_KEY")
    enum_parser.add_argument("--batch-size", type=int, default=200)
    enum_parser.add_argument(
        "--raw-dir", required=True,
        help="external directory for immutable PubMed XML response batches",
    )
    enum_parser.set_defaults(func=command_enumerate)

    validate_parser = subparsers.add_parser(
        "validate-registry", help="check that each journal query has PubMed hits"
    )
    validate_parser.add_argument("--journals", default=str(DEFAULT_JOURNALS))
    validate_parser.add_argument("--journal", default="all", help="registry key or 'all'")
    validate_parser.add_argument("--start", required=True)
    validate_parser.add_argument("--end", required=True)
    validate_parser.add_argument("--email", required=True, help="contact email sent to NCBI")
    validate_parser.add_argument("--api-key-env", default="NCBI_API_KEY")
    validate_parser.set_defaults(func=command_validate_registry)

    screen_parser = subparsers.add_parser("screen", help="apply recall-oriented deterministic rules")
    screen_parser.add_argument("--db", required=True)
    screen_parser.add_argument("--rules", default=str(DEFAULT_RULES))
    screen_parser.set_defaults(func=command_screen)

    export_parser = subparsers.add_parser("export-llm-queue", help="export title/abstract JSONL")
    export_parser.add_argument("--db", required=True)
    export_parser.add_argument("--out", required=True)
    export_parser.set_defaults(func=command_export_llm)

    calibration_parser = subparsers.add_parser("create-calibration-sample", help="create the locked Step 3 calibration sample")
    calibration_parser.add_argument("--db", required=True)
    calibration_parser.add_argument("--seed", default="article-blueprint-os-step3-calibration-v1")
    calibration_parser.add_argument("--prompt-version", default="v1")
    calibration_parser.set_defaults(func=command_create_calibration)

    calibration_export_parser = subparsers.add_parser("export-calibration-queue", help="export a calibration JSONL queue externally")
    calibration_export_parser.add_argument("--db", required=True)
    calibration_export_parser.add_argument("--calibration-id", required=True)
    calibration_export_parser.add_argument("--out", required=True)
    calibration_export_parser.set_defaults(func=command_export_calibration)

    web_parser = subparsers.add_parser(
        "prepare-web-calibration-batches",
        help="prepare manual-only external Web calibration packets",
    )
    web_parser.add_argument("--db", required=True)
    web_parser.add_argument("--calibration-id", required=True)
    web_parser.add_argument("--out", required=True)
    web_parser.add_argument("--batch-size", type=int, default=20)
    web_parser.add_argument("--software-revision", required=True)
    web_parser.set_defaults(func=command_prepare_web_batches)

    web_validate_parser = subparsers.add_parser(
        "validate-web-calibration-batch",
        help="validate and import one manual Web calibration output",
    )
    web_validate_parser.add_argument("--db", required=True)
    web_validate_parser.add_argument("--manifest", required=True)
    web_validate_parser.add_argument("--output", required=True)
    web_validate_parser.add_argument("--model-display-name", required=True)
    web_validate_parser.add_argument("--operator", required=True)
    web_validate_parser.add_argument("--executed-at", required=True)
    web_validate_parser.add_argument("--fresh-chat-confirmed", action="store_true")
    web_validate_parser.add_argument("--attempt", type=int, default=1)
    web_validate_parser.add_argument("--execution-mode", choices=("manual", "automated_browser"), default="manual")
    web_validate_parser.set_defaults(func=command_validate_web_batch)

    import_parser = subparsers.add_parser("import-llm-results", help="validate and import LLM JSONL")
    import_parser.add_argument("--db", required=True)
    import_parser.add_argument("--input", required=True)
    import_parser.set_defaults(func=command_import_llm)

    audit_parser = subparsers.add_parser("sample-no-audit", help="sample latest LLM NO decisions")
    audit_parser.add_argument("--db", required=True)
    audit_parser.add_argument("--fraction", type=float, default=0.10)
    audit_parser.add_argument("--seed", default="article-blueprint-os-v1")
    audit_parser.set_defaults(func=command_sample_audit)

    status_parser = subparsers.add_parser("status", help="show compact corpus counts")
    status_parser.add_argument("--db", required=True)
    status_parser.set_defaults(func=command_status)

    backfill_parser = subparsers.add_parser(
        "historical-backfill",
        help="run or resume the complete journal registry backfill",
    )
    backfill_parser.add_argument("--db", required=True)
    backfill_parser.add_argument("--journals", default=str(DEFAULT_JOURNALS))
    backfill_parser.add_argument("--start", required=True)
    backfill_parser.add_argument("--end", required=True)
    backfill_parser.add_argument("--email", required=True, help="contact email sent to NCBI")
    backfill_parser.add_argument("--api-key-env", default="NCBI_API_KEY")
    backfill_parser.add_argument("--batch-size", type=int, default=200)
    backfill_parser.add_argument("--raw-dir", required=True)
    backfill_parser.add_argument("--report")
    backfill_parser.add_argument("--resume-id")
    backfill_parser.add_argument(
        "--software-revision",
        help="git SHA or release identifier; defaults to the current repository HEAD",
    )
    backfill_parser.set_defaults(func=command_historical_backfill)

    report_parser = subparsers.add_parser(
        "coverage-report", help="export a stored Step 2 aggregate coverage report"
    )
    report_parser.add_argument("--db", required=True)
    report_parser.add_argument("--backfill-id", required=True)
    report_parser.add_argument("--out", required=True)
    report_parser.set_defaults(func=command_coverage_report)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)
