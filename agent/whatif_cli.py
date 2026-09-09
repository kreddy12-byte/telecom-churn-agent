"""Command-line entrypoint for the what-if simulator.

    python -m agent.whatif_cli --customer-id 7590-VHVEG

Runs the real saved model and the real SHAP explainer over every applicable
scenario, ranks them, and prints the comparison. Uses the LLM for interpretation
when one is configured; otherwise the deterministic interpretation is used and
the report says so.
"""

from __future__ import annotations

import argparse
import json
import sys

from agent.providers.llm_provider import build_provider
from agent.services.whatif_service import (
    run_whatif_analysis,
    run_whatif_analysis_for_dataset_customer,
)
from agent.simulation.report import render_whatif_report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run what-if retention scenarios for one customer."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--customer-id", default=None, help="customerID from the raw dataset.")
    source.add_argument("--json", dest="payload", default=None, help="Customer record as JSON.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Force the deterministic interpretation even when an LLM is configured.",
    )
    parser.add_argument(
        "--json-output", action="store_true", help="Print JSON instead of a report."
    )
    return parser.parse_args()


def _use_utf8_stdout() -> None:
    """Windows terminals default to a code page that mangles the em dash used in
    the what-if disclaimer, so print as UTF-8 where the stream allows it."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    _use_utf8_stdout()
    args = _parse_args()
    provider = None if args.no_llm else build_provider()

    if args.customer_id:
        result = run_whatif_analysis_for_dataset_customer(args.customer_id, provider=provider)
    else:
        result = run_whatif_analysis(json.loads(args.payload), provider=provider)

    if args.json_output:
        print(result.model_dump_json(indent=2))
    else:
        print(render_whatif_report(result))


if __name__ == "__main__":
    main()
