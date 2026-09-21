Traceability Task: DEV-008
Traceability Level: T2

Implement the locked CMP-003 / ADR-006 attempt controller. Previously the gateway
blocked implementation purposes; it now requires an exclusive durable reservation
and consumes capacity only on affirmative accepted-execution evidence. Two failed
deterministic checkpoints atomically close the scope, and every subsequent
controlled invocation is rejected before AIRuntimePort.

SQLite schema 3 preserves existing v1/v2 invocation and DEV-outcome evidence,
enforces one open attempt across processes and restarts, and records governed
continuation and successor provenance. Canonical max_attempts is 2; the watchdog
remains 600 seconds. Unknown usage stays unknown. TEST-008 records deterministic
fake-port, concurrency, migration, telemetry regression, and governance evidence.

- [x] I acknowledge this is a material design change and have linked the required design + decision/contract + verification evidence.
