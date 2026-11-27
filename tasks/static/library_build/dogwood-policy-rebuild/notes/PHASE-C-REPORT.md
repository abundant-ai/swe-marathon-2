# Dogwood rebuild: Phase C report (2026-11-27)

Author notes, never shipped. Phase C takes the task to QA-ready. The coordinator's scope was:
- the agent-facing material;
- the gaps Phase B named (V near-miss pairs, more K shapes, `format` and `schema` cases);
- the coverage inventory and kill matrix, the stub zoo, the leak scan and a 3+1 determinism run;
- calibration;
- the close-out: bundle, hashes, preflight and backups.

Everything ran in local Docker Desktop (linux/arm64) under the shared heavy lock. Nothing touched
Oddish.

PENDING
