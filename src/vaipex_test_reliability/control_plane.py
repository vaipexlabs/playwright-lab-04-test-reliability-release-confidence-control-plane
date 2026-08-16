"""Collect, correlate, govern, and decide Playwright release confidence."""

import argparse
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from vaipex_test_reliability.server import PROJECT_ROOT, reference_application

POLICY_PATH = PROJECT_ROOT / "policies" / "release-confidence.json"
QUARANTINE_PATH = PROJECT_ROOT / "policies" / "quarantines.json"
REPORT_ROOT = PROJECT_ROOT / "reports"
ARTIFACT_ROOT = PROJECT_ROOT / "artifacts" / "runs"

JOURNEYS: tuple[dict[str, Any], ...] = (
    {
        "id": "checkout.stable",
        "name": "Stable checkout",
        "scenario": "stable",
        "critical": True,
        "owner": "Commerce Platform",
        "profiles": ("healthy", "incident"),
    },
    {
        "id": "checkout.transient",
        "name": "Transient checkout recovery",
        "scenario": "transient",
        "critical": False,
        "owner": "Commerce Platform",
        "profiles": ("healthy", "incident"),
    },
    {
        "id": "checkout.critical-failure",
        "name": "Critical payment failure",
        "scenario": "critical-failure",
        "critical": True,
        "owner": "Commerce Platform",
        "profiles": ("incident",),
    },
)


class ReliabilityPolicyError(RuntimeError):
    """Raised when evidence or governance policy is invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")


def classify_attempts(attempts: list[dict[str, Any]]) -> str:
    """Classify complete ordered attempts without hiding a recovered failure."""

    if not attempts:
        raise ReliabilityPolicyError("A journey must contain at least one attempt.")
    statuses = [attempt.get("status") for attempt in attempts]
    if any(status not in {"passed", "failed"} for status in statuses):
        raise ReliabilityPolicyError("Attempt status must be passed or failed.")
    if statuses[0] == "passed":
        return "stable"
    if statuses[-1] == "passed":
        return "flaky"
    return "failed"


def validate_quarantines(
    payload: dict[str, Any], *, today: date | None = None
) -> dict[str, dict[str, str]]:
    """Validate narrow, owned, time-bounded quarantine governance."""

    if payload.get("schema_version") != 1 or not isinstance(
        payload.get("quarantines"), list
    ):
        raise ReliabilityPolicyError("Quarantine policy uses an invalid schema.")
    current_date = today or date.today()
    required = {"journey_id", "owner", "reason", "issue_url", "expires_on"}
    known_journeys = {journey["id"] for journey in JOURNEYS}
    validated: dict[str, dict[str, str]] = {}
    for index, quarantine in enumerate(payload["quarantines"], start=1):
        if not isinstance(quarantine, dict) or not required.issubset(quarantine):
            raise ReliabilityPolicyError(
                f"Quarantine {index} must define {', '.join(sorted(required))}."
            )
        if any(
            not isinstance(quarantine[key], str) or not quarantine[key].strip()
            for key in required
        ):
            raise ReliabilityPolicyError(f"Quarantine {index} contains an empty field.")
        journey_id = quarantine["journey_id"]
        if journey_id in {"*", "all"} or journey_id not in known_journeys:
            raise ReliabilityPolicyError(
                f"Quarantine {index} targets an unknown or broad journey."
            )
        if journey_id in validated:
            raise ReliabilityPolicyError(f"Journey {journey_id} is quarantined twice.")
        if not quarantine["issue_url"].startswith("https://"):
            raise ReliabilityPolicyError(
                f"Quarantine {index} must reference an HTTPS issue URL."
            )
        try:
            expiry = date.fromisoformat(quarantine["expires_on"])
        except ValueError as error:
            raise ReliabilityPolicyError(
                f"Quarantine {index} has an invalid expiration date."
            ) from error
        if expiry < current_date:
            raise ReliabilityPolicyError(
                f"Quarantine for {journey_id} expired on {expiry}."
            )
        validated[journey_id] = quarantine
    return validated


def apply_quarantines(
    journeys: list[dict[str, Any]], quarantines: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    """Apply approved quarantine metadata while preserving original outcome."""

    governed: list[dict[str, Any]] = []
    for journey in journeys:
        item = dict(journey)
        quarantine = quarantines.get(item["id"])
        item["raw_classification"] = item["classification"]
        item["quarantine"] = quarantine
        if quarantine and item["classification"] in {"flaky", "failed"}:
            item["classification"] = "quarantined"
        governed.append(item)
    return governed


def merge_shards(shards: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a complete shard set without losing or duplicating journey identity."""

    if not shards:
        raise ReliabilityPolicyError("At least one shard is required.")
    profile = shards[0].get("profile")
    shard_count = shards[0].get("shard_count")
    expected_indices = (
        set(range(shard_count)) if isinstance(shard_count, int) else set()
    )
    actual_indices = {shard.get("shard_index") for shard in shards}
    if not expected_indices or actual_indices != expected_indices:
        raise ReliabilityPolicyError(
            f"Shard set is incomplete: expected={sorted(expected_indices)}, "
            f"actual={sorted(actual_indices)}."
        )
    if any(
        shard.get("profile") != profile or shard.get("shard_count") != shard_count
        for shard in shards
    ):
        raise ReliabilityPolicyError("Shard contracts do not describe one run.")

    journeys: list[dict[str, Any]] = []
    identities: set[str] = set()
    for shard in sorted(shards, key=lambda item: item["shard_index"]):
        for journey in shard.get("journeys", []):
            if journey["id"] in identities:
                raise ReliabilityPolicyError(
                    f"Journey {journey['id']} appears in more than one shard."
                )
            identities.add(journey["id"])
            journeys.append(journey)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "journeys": sorted(journeys, key=lambda item: item["id"]),
        "profile": profile,
        "schema_version": 1,
        "shard_count": shard_count,
    }


def evaluate_release(
    *,
    evidence: dict[str, Any],
    policy: dict[str, Any],
    quarantine_payload: dict[str, Any],
    today: date | None = None,
) -> dict[str, Any]:
    """Evaluate correlated journey evidence into RELEASE or HOLD."""

    quarantines = validate_quarantines(quarantine_payload, today=today)
    journeys = apply_quarantines(evidence["journeys"], quarantines)
    total = len(journeys)
    if total == 0:
        raise ReliabilityPolicyError("Release evidence contains no journeys.")

    counts = {
        name: sum(item["classification"] == name for item in journeys)
        for name in ("stable", "flaky", "failed", "quarantined")
    }
    completed = counts["stable"] + counts["flaky"] + counts["quarantined"]
    completion_rate = completed / total
    flake_rate = counts["flaky"] / total
    blockers: list[str] = []
    if completion_rate < policy["minimum_completion_rate"]:
        blockers.append(
            f"completion rate {completion_rate:.3f} is below "
            f"{policy['minimum_completion_rate']:.3f}"
        )
    if flake_rate > policy["max_flake_rate"]:
        blockers.append(
            f"flake rate {flake_rate:.3f} exceeds {policy['max_flake_rate']:.3f}"
        )
    if counts["failed"] > policy["max_failed_journeys"]:
        blockers.append(
            f"failed journeys {counts['failed']} exceed {policy['max_failed_journeys']}"
        )
    if counts["quarantined"] > policy["max_active_quarantines"]:
        blockers.append(
            f"active quarantines {counts['quarantined']} exceed "
            f"{policy['max_active_quarantines']}"
        )

    if policy["critical_journeys_must_pass"]:
        for journey in journeys:
            if not journey["critical"]:
                continue
            raw = journey["raw_classification"]
            if raw == "failed":
                blockers.append(f"critical journey {journey['id']} failed")
            if (
                journey["classification"] == "quarantined"
                and not policy["allow_critical_quarantine"]
            ):
                blockers.append(
                    f"critical journey {journey['id']} cannot be quarantined"
                )

    decision = "HOLD" if blockers else "RELEASE"
    return {
        "blockers": sorted(set(blockers)),
        "counts": counts,
        "decision": decision,
        "generated_at": datetime.now(UTC).isoformat(),
        "journeys": journeys,
        "metrics": {
            "completion_rate": round(completion_rate, 4),
            "flake_rate": round(flake_rate, 4),
        },
        "policy": policy,
        "profile": evidence["profile"],
        "schema_version": 1,
        "status": "passed" if decision == "RELEASE" else "failed",
    }


def _execute_journey(
    *, browser: Any, base_url: str, journey: dict[str, Any], profile: str
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for attempt_number in (1, 2):
        context = browser.new_context(
            viewport={"width": 1280, "height": 820},
            color_scheme="light",
            locale="en-US",
            reduced_motion="reduce",
            timezone_id="UTC",
        )
        page = context.new_page()
        started_at = datetime.now(UTC)
        try:
            page.goto(
                f"{base_url}/?scenario={journey['scenario']}",
                wait_until="networkidle",
            )
            page.get_by_role("button", name="Complete order").click()
            result = page.locator("#checkout-result")
            result.wait_for(state="visible")
            title = result.locator("[data-result-title]").inner_text()
            detail = result.locator("[data-result-detail]").inner_text()
            passed = title == "Order confirmed"
            screenshot_path = (
                ARTIFACT_ROOT
                / profile
                / journey["id"]
                / f"attempt-{attempt_number}.png"
            )
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=screenshot_path, full_page=True)
            attempts.append(
                {
                    "attempt": attempt_number,
                    "detail": detail,
                    "duration_ms": round(
                        (datetime.now(UTC) - started_at).total_seconds() * 1000
                    ),
                    "screenshot": screenshot_path.relative_to(PROJECT_ROOT).as_posix(),
                    "status": "passed" if passed else "failed",
                    "title": title,
                }
            )
            if passed:
                break
        finally:
            context.close()
    return {
        "attempts": attempts,
        "classification": classify_attempts(attempts),
        "critical": journey["critical"],
        "id": journey["id"],
        "name": journey["name"],
        "owner": journey["owner"],
        "scenario": journey["scenario"],
    }


def run_shard(*, profile: str, shard_index: int, shard_count: int) -> dict[str, Any]:
    """Execute one deterministic subset of the profile journey catalog."""

    if profile not in {"healthy", "incident"}:
        raise ReliabilityPolicyError(f"Unknown execution profile: {profile}.")
    if shard_count < 1 or not 0 <= shard_index < shard_count:
        raise ReliabilityPolicyError("Shard index must be within the shard count.")
    candidates = [journey for journey in JOURNEYS if profile in journey["profiles"]]
    selected = [
        journey
        for position, journey in enumerate(candidates)
        if position % shard_count == shard_index
    ]
    journeys: list[dict[str, Any]] = []
    with reference_application() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for journey in selected:
                journeys.append(
                    _execute_journey(
                        browser=browser,
                        base_url=base_url,
                        journey=journey,
                        profile=profile,
                    )
                )
        finally:
            browser.close()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "journeys": journeys,
        "profile": profile,
        "schema_version": 1,
        "shard_count": shard_count,
        "shard_index": shard_index,
    }


def render_report(report: dict[str, Any], path: Path) -> None:
    """Render a portable review dashboard without external dependencies."""

    template_dir = PROJECT_ROOT / "src" / "vaipex_test_reliability" / "templates"
    environment = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template("release-report.html")
    document = template.render(
        report=report,
        decision_class="release" if report["decision"] == "RELEASE" else "hold",
        blockers=report["blockers"] or ["No policy blockers detected"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document)


def _command_run_shard(args: argparse.Namespace) -> int:
    report = run_shard(
        profile=args.profile,
        shard_index=args.shard_index,
        shard_count=args.shard_count,
    )
    _write_json(args.output, report)
    for journey in report["journeys"]:
        print(
            f"{journey['classification'].upper():6} {journey['id']}: "
            f"{len(journey['attempts'])} attempt(s)"
        )
    print(f"Shard evidence: {args.output}")
    return 0


def _command_merge(args: argparse.Namespace) -> int:
    report = merge_shards([_load_json(path) for path in args.inputs])
    _write_json(args.output, report)
    print(
        f"Merged {report['shard_count']} shard(s) and "
        f"{len(report['journeys'])} journey result(s)."
    )
    print(f"Correlated evidence: {args.output}")
    return 0


def _command_decide(args: argparse.Namespace) -> int:
    report = evaluate_release(
        evidence=_load_json(args.input),
        policy=_load_json(args.policy),
        quarantine_payload=_load_json(args.quarantines),
    )
    _write_json(args.output, report)
    render_report(report, args.html)
    print(f"Release confidence decision: {report['decision']}")
    for blocker in report["blockers"]:
        print(f"  BLOCKER: {blocker}")
    print(f"Machine-readable decision: {args.output}")
    print(f"Review dashboard: {args.html}")
    if args.expect and report["decision"].lower() != args.expect:
        print(
            f"ERROR: expected {args.expect.upper()}, received {report['decision']}",
            file=sys.stderr,
        )
        return 2
    return 0 if report["decision"] == "RELEASE" or args.expect == "hold" else 1


def main() -> int:
    """Run the reliability control-plane command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    shard_parser = subparsers.add_parser("run-shard")
    shard_parser.add_argument(
        "--profile", choices=("healthy", "incident"), required=True
    )
    shard_parser.add_argument("--shard-index", type=int, required=True)
    shard_parser.add_argument("--shard-count", type=int, required=True)
    shard_parser.add_argument("--output", type=Path, required=True)
    shard_parser.set_defaults(handler=_command_run_shard)

    merge_parser = subparsers.add_parser("merge")
    merge_parser.add_argument("--output", type=Path, required=True)
    merge_parser.add_argument("inputs", type=Path, nargs="+")
    merge_parser.set_defaults(handler=_command_merge)

    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--input", type=Path, required=True)
    decide_parser.add_argument("--output", type=Path, required=True)
    decide_parser.add_argument("--html", type=Path, required=True)
    decide_parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    decide_parser.add_argument("--quarantines", type=Path, default=QUARANTINE_PATH)
    decide_parser.add_argument("--expect", choices=("release", "hold"))
    decide_parser.set_defaults(handler=_command_decide)

    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, json.JSONDecodeError, ReliabilityPolicyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
