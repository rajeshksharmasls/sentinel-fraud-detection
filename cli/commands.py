"""
Sentinel CLI commands.

Commands: health, policies, investigate, status, approve, reject, demo
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .client import SentinelAPIClient


def print_json(data: object) -> None:
    """Pretty-print JSON."""

    print(json.dumps(data, indent=2, default=str))


def command_health(client: SentinelAPIClient) -> int:
    """Check API health."""

    try:

        result = client.health()
        print_json(result)
        return 0

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_policies(client: SentinelAPIClient) -> int:
    """List policy rules."""

    try:

        result = client.policies()
        print_json(result)
        return 0

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_investigate(
    client: SentinelAPIClient,
    account_id: str,
    wait: bool,
) -> int:
    """Submit investigation."""

    try:

        result = client.submit_investigation(account_id)
        print("\nInvestigation submitted.")
        print_json(result)

        if not wait:
            return 0

        job_id = result["job_id"]
        print("\nWaiting for investigation...")

        return wait_for_completion(client, job_id)

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def wait_for_completion(
    client: SentinelAPIClient,
    job_id: str,
    interval: float = 2.0,
) -> int:
    """Wait for investigation to complete."""

    terminal_states = {"completed", "failed"}

    while True:

        result = client.get_investigation(job_id)
        status = result.get("status")

        print(f"  status: {status}")

        if status in terminal_states:

            print("\nFinal result:")
            print_json(result)

            return 0 if status == "completed" else 1

        if status == "waiting_approval":

            print("\nInvestigation requires human approval.")
            print_json(result)

            return 0

        time.sleep(interval)


def command_status(
    client: SentinelAPIClient,
    job_id: str,
) -> int:
    """Get investigation status."""

    try:

        result = client.get_investigation(job_id)
        print_json(result)
        return 0

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_approve(
    client: SentinelAPIClient,
    job_id: str,
    reason: str,
) -> int:
    """Approve investigation."""

    try:

        result = client.approve(job_id, reason)
        print("\nInvestigation approved.")
        print_json(result)
        return 0

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_reject(
    client: SentinelAPIClient,
    job_id: str,
    reason: str,
) -> int:
    """Reject investigation."""

    try:

        result = client.reject(job_id, reason)
        print("\nInvestigation rejected.")
        print_json(result)
        return 0

    except Exception as exc:

        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def command_demo(client: SentinelAPIClient) -> int:
    """Run interactive demo."""

    print()
    print("=" * 60)
    print(" SENTINEL FRAUD INVESTIGATION DEMO")
    print("=" * 60)
    print()

    print("1. Checking API...")
    try:
        result = client.health()
        print_json(result)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print("2. Listing policies...")
    try:
        result = client.policies()
        print_json(result)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print("3. Submitting investigation for A00985...")
    try:
        result = client.submit_investigation("A00985")
        print_json(result)
        job_id = result["job_id"]
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"4. Job ID: {job_id}")
    print("5. Polling investigation...")

    return wait_for_completion(client, job_id)


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""

    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Sentinel Fraud Investigation Agent",
    )

    parser.add_argument(
        "--url",
        default=None,
        help="Sentinel API URL. Defaults to SENTINEL_API_URL.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # health
    subparsers.add_parser("health", help="Check API health.")

    # policies
    subparsers.add_parser("policies", help="List policy rules.")

    # investigate
    investigate = subparsers.add_parser(
        "investigate",
        help="Submit fraud investigation.",
    )
    investigate.add_argument("account_id", help="Account to investigate.")
    investigate.add_argument(
        "--wait",
        action="store_true",
        help="Wait until complete or approval.",
    )

    # status
    status = subparsers.add_parser("status", help="Get investigation status.")
    status.add_argument("job_id")

    # approve
    approve = subparsers.add_parser("approve", help="Approve investigation.")
    approve.add_argument("job_id")
    approve.add_argument("--reason", default="Approved by analyst.")

    # reject
    reject = subparsers.add_parser("reject", help="Reject investigation.")
    reject.add_argument("job_id")
    reject.add_argument("--reason", default="Rejected by analyst.")

    # demo
    subparsers.add_parser("demo", help="Run interactive demo.")

    return parser


def main() -> int:
    """Main CLI entry point."""

    parser = build_parser()
    args = parser.parse_args()

    client = SentinelAPIClient(base_url=args.url)

    if args.command == "health":
        return command_health(client)

    if args.command == "policies":
        return command_policies(client)

    if args.command == "investigate":
        return command_investigate(client, args.account_id, args.wait)

    if args.command == "status":
        return command_status(client, args.job_id)

    if args.command == "approve":
        return command_approve(client, args.job_id, args.reason)

    if args.command == "reject":
        return command_reject(client, args.job_id, args.reason)

    if args.command == "demo":
        return command_demo(client)

    parser.print_help()

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
