from datetime import date

import pytest

from vaipex_test_reliability.control_plane import (
    ReliabilityPolicyError,
    classify_attempts,
    evaluate_release,
    merge_shards,
    validate_quarantines,
)


def _journey(
    journey_id: str,
    classification: str,
    *,
    critical: bool = False,
) -> dict:
    statuses = {
        "stable": ["passed"],
        "flaky": ["failed", "passed"],
        "failed": ["failed", "failed"],
    }[classification]
    return {
        "attempts": [
            {"attempt": index, "status": status}
            for index, status in enumerate(statuses, start=1)
        ],
        "classification": classification,
        "critical": critical,
        "id": journey_id,
        "name": journey_id,
        "owner": "Commerce Platform",
        "scenario": journey_id,
    }


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["passed"], "stable"),
        (["failed", "passed"], "flaky"),
        (["failed", "failed"], "failed"),
    ],
)
def test_attempt_classification_preserves_retry_history(
    statuses: list[str], expected: str
) -> None:
    attempts = [
        {"attempt": index, "status": status}
        for index, status in enumerate(statuses, start=1)
    ]

    assert classify_attempts(attempts) == expected


def test_merge_requires_every_shard_and_unique_identity() -> None:
    merged = merge_shards(
        [
            {
                "profile": "healthy",
                "shard_count": 2,
                "shard_index": 0,
                "journeys": [_journey("checkout.stable", "stable")],
            },
            {
                "profile": "healthy",
                "shard_count": 2,
                "shard_index": 1,
                "journeys": [_journey("checkout.transient", "flaky")],
            },
        ]
    )

    assert [item["id"] for item in merged["journeys"]] == [
        "checkout.stable",
        "checkout.transient",
    ]


def test_incomplete_shard_set_is_rejected() -> None:
    with pytest.raises(ReliabilityPolicyError, match="incomplete"):
        merge_shards(
            [
                {
                    "profile": "healthy",
                    "shard_count": 2,
                    "shard_index": 0,
                    "journeys": [],
                }
            ]
        )


def test_expired_quarantine_is_rejected() -> None:
    with pytest.raises(ReliabilityPolicyError, match="expired"):
        validate_quarantines(
            {
                "schema_version": 1,
                "quarantines": [
                    {
                        "journey_id": "checkout.transient",
                        "owner": "Commerce Platform",
                        "reason": "Tracked instability",
                        "issue_url": "https://github.com/vaipexlabs/example/issues/1",
                        "expires_on": "2026-08-15",
                    }
                ],
            },
            today=date(2026, 8, 16),
        )


def test_healthy_evidence_releases_with_visible_flake() -> None:
    report = evaluate_release(
        evidence={
            "profile": "healthy",
            "journeys": [
                _journey("checkout.stable", "stable", critical=True),
                _journey("checkout.transient", "flaky"),
            ],
        },
        policy={
            "minimum_completion_rate": 1.0,
            "max_flake_rate": 0.5,
            "max_failed_journeys": 0,
            "max_active_quarantines": 1,
            "critical_journeys_must_pass": True,
            "allow_critical_quarantine": False,
        },
        quarantine_payload={"schema_version": 1, "quarantines": []},
        today=date(2026, 8, 16),
    )

    assert report["decision"] == "RELEASE"
    assert report["counts"]["flaky"] == 1


def test_critical_failure_holds_release() -> None:
    report = evaluate_release(
        evidence={
            "profile": "incident",
            "journeys": [
                _journey("checkout.stable", "stable", critical=True),
                _journey("checkout.critical-failure", "failed", critical=True),
            ],
        },
        policy={
            "minimum_completion_rate": 0.5,
            "max_flake_rate": 0.5,
            "max_failed_journeys": 1,
            "max_active_quarantines": 1,
            "critical_journeys_must_pass": True,
            "allow_critical_quarantine": False,
        },
        quarantine_payload={"schema_version": 1, "quarantines": []},
        today=date(2026, 8, 16),
    )

    assert report["decision"] == "HOLD"
    assert "critical journey checkout.critical-failure failed" in report["blockers"]
