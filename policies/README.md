# Reliability Policies

The files in this directory are versioned release-confidence contracts.

- `release-confidence.json` defines completion, flake, failure, quarantine,
  and critical-journey thresholds.
- `quarantines.json` is the temporary exception register. Every entry must name
  one journey, owner, reason, issue URL, and expiration date.

Quarantine is visible debt, not a way to turn a failed test green. Broad,
duplicate, incomplete, expired, or unauthorized critical-journey quarantines
fail governance validation.
