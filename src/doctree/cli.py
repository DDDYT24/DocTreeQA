"""Command line entry point."""

import argparse
import json
import sys

from doctree.config import load_config
from doctree.generator import generate
from doctree.pipeline import check
from doctree.reporting import build_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctree")
    parser.add_argument("--config", default="configs/default.yaml")
    commands = parser.add_subparsers(dest="command", required=True)
    gen = commands.add_parser("generate", help="Generate explicitly synthetic example inputs")
    gen.add_argument("--force", action="store_true")
    check_parser = commands.add_parser(
        "check", help="Validate inputs and score against ground truth when available"
    )
    check_parser.add_argument("--fail-on-issues", action="store_true")
    report_parser = commands.add_parser(
        "report", help="Run fresh checks and export an Excel workbook"
    )
    report_parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "generate":
            result = generate(config, force=args.force)
        elif args.command == "check":
            result = check(config)
        else:
            result = build_report(config, force=args.force)
        print(json.dumps(result, indent=2))
        if args.command == "check" and args.fail_on_issues and result["issue_count"]:
            return 1
        return 0
    except (OSError, ValueError) as exc:
        print(f"doctree: {exc}", file=sys.stderr)
        return 2
