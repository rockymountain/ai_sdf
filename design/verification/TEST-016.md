---
id: TEST-016
kind: verification
title: Accountable human-review evidence verification
status: proposed
version: 1
verification_type: integration
---

# Verification contract

After ADR-011 owner acceptance selects an evidence source and DEV-016 is implemented,
TEST-016 must prove:

- required review evidence exists and comes from the accepted authoritative source;
- reviewer identity is explicit and the reviewer is authorized;
- evidence binds to the exact governed revision or change;
- approval and rejection dispositions are explicit and rejection blocks;
- stale, replayed, ambiguous, unauthorized, and contract-invalid self-approval
  evidence fails closed;
- deterministic PASS is never interpreted as human approval;
- runtime `HumanAuthorization` is not silently substituted;
- semantic-risk and level-classification judgment remains human-owned.

# Source-specific completion condition

The final fixtures and integration boundary cannot be selected until ADR-011 names
the accepted evidence source, authority rule, and self-approval behavior. This
contract therefore defines invariant assertions without claiming current
implementation readiness.

# Lifecycle boundary

TEST-016 is proposed. It records no current PASS and authorizes no implementation,
M3 window, or gate promotion.
