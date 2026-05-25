# Feature specifications (SDD)

This directory holds **Spec-Driven Development (SDD)** artifacts: the spec is the source of truth; implementation and tests trace back to acceptance criteria.

## Workflow (Spec + Harness)

| Phase | Artifact | Purpose |
|-------|----------|---------|
| 1. Specify | `spec.md` | What / why / what NOT; user scenarios; acceptance criteria |
| 2. Plan | `plan.md` | Architecture, file map, env vars, API contract |
| 3. Tasks | `tasks.md` | Dependency-ordered, reviewable work units |
| 4. Harness | `harness.md` | Automated gates + manual QA that prove spec compliance |
| 5. Implement | Code + tests | Only after spec/plan/tasks are reviewed |

Agents implementing a feature should read **spec → plan → tasks → harness** before writing code.

## Active features

| Feature | Branch | Status |
|---------|--------|--------|
| [MT5 Thin Gateway](mt5-thin-gateway/) | `feat/mt5-thin-gateway` | In progress |
