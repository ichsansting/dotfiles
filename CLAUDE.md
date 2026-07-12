## Development workflow

**Trunk-based development**
- Commit directly to `main`, or use short-lived branches merged within a day — no long-lived feature branches.
- Small, frequent commits over large batched changes.
- Keep `main` always in a working state; don't merge broken or half-finished work. Use feature flags if incomplete work must land.

**Lean principles**
- Eliminate waste: no speculative code, docs, or abstractions ahead of actual need.
- Decide as late as possible: don't lock in design choices until forced to by a real requirement (matches `docs/agents/domain.md` — ADRs/`CONTEXT.md` are created lazily, not upfront).
- Deliver fast: small commits/changes, tight feedback loops, validate early rather than batching up big releases.
- Build integrity in: tests and review happen alongside the work, not bolted on after.

## Agent skills

### Issue tracker

Local markdown under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical roles (needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context (root `CONTEXT.md` + `docs/adr/`). See `docs/agents/domain.md`.
