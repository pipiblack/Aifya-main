# Contributing to Aifya

> **Akili kwa Afya** — Intelligence for Health

Aifya is an AI-native Hospital Management System for Kenyan hospitals. Because real patient care depends on this code, we follow a strict but lightweight workflow.

---

## Quick Reference

| | Branch | Use for |
|---|---|---|
| **Production** | `main` | Deployed to facilities. Always green. |
| **Integration** | `develop` | Where features merge first. Always buildable. |
| **Feature work** | `feat/<scope>` | New features. Branch from `develop`. |
| **Bug fixes (non-prod)** | `fix/<scope>` | Bugs found before release. Branch from `develop`. |
| **Hotfixes (prod)** | `hotfix/<scope>` | Urgent production fixes. Branch from `main`. |
| **Chores** | `chore/<scope>` | Dev tooling, deps, docs. Branch from `develop`. |

---

## Branch Strategy

```
main      ──────●─────────●──────────●──→  (tagged releases v1.0, v1.1)
                ↑         ↑          ↑
develop   ─●────●──●──●───●──●───────●──→  (integration branch)
           ↑       ↑      ↑       ↑
feat/*    ─●───────●──────●──────●──→      (your work happens here)
```

### Standard flow (features, bugs, chores)

```bash
git checkout develop
git pull origin develop

git checkout -b feat/scribe-mobile      # or fix/, chore/
# ... make changes, commit ...
git push -u origin feat/scribe-mobile

# Open PR: feat/scribe-mobile → develop
```

### Hotfix flow (production-critical bugs only)

```bash
git checkout main
git pull origin main

git checkout -b hotfix/paye-calc-rounding
# ... fix the bug, add a regression test ...
git push -u origin hotfix/paye-calc-rounding

# Open TWO PRs:
#   1. hotfix/paye-calc-rounding → main    (fast-track review, deploys to prod)
#   2. hotfix/paye-calc-rounding → develop (so the fix isn't lost on next release)
```

### Release flow (integrate develop into main)

```bash
# Open PR: develop → main
# Title: "release: v1.1.0 — Finance + HR/Payroll"
# Body: changelog summarising what's shipping
# After merge, tag the release on main:
git checkout main && git pull
git tag -a v1.1.0 -m "Finance + HR/Payroll modules"
git push origin v1.1.0
```

---

## Commit Messages

Format: `type(scope): short description`

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `style`, `ci`, `revert`

**Examples:**

```
feat(finance): add bank reconciliation auto-match
fix(payroll): correct PAYE rounding for taxable pay near band boundary
docs(readme): update Kenya statutory rates table for Feb 2026
chore(deps): bump fastapi to 0.115.5
refactor(scribe): extract whisper client into reusable service
test(billing): add edge case for waiver > invoice total
perf(reports): index transaction_entries on (account_id, period_id)
ci(github): add gitleaks secrets scan to PR pipeline
```

Body (when needed) should explain **why**, not what — the diff already shows what.

---

## Pull Request Rules

### Required for every PR

- [ ] Linked issue (if applicable) — use `Closes #123` in the description
- [ ] CI passes (lint + typecheck + tests + secrets-scan)
- [ ] At least 1 reviewer approval
- [ ] No merge conflicts with base branch
- [ ] Description explains the "why", not just the "what"

### Additional for clinical / safety-impacting changes

- [ ] Clinical safety review noted in PR description
- [ ] Tests cover the failure mode
- [ ] CLAUDE.md rules followed (event sourcing, audit log, soft delete)
- [ ] No PHI in test fixtures or sample data

### Additional for finance / payroll changes

- [ ] DR=CR validation preserved
- [ ] Idempotency keys honoured
- [ ] Period locks respected
- [ ] Worked example test added if calculations changed
- [ ] Statutory rates remain configuration (not hardcoded)

---

## Code Quality Bar

These are enforced in CI — PRs that violate them fail automatically.

### TypeScript (frontend)

- Zero `any` types
- `tsc --noEmit` must pass
- ESLint must pass
- Vitest unit tests must pass

### Python (backend)

- Full type hints on every public function
- No bare `except:` — always catch specific exceptions
- `ruff check .` and `ruff format --check .` must pass
- `mypy app` must pass (currently soft-fail; will harden after Q3 2026)
- `pytest` must pass

### Go (services)

- `go vet ./...` must pass
- `go test -race ./...` must pass
- `golangci-lint` must pass

---

## Security Rules (non-negotiable)

- **Never commit secrets.** `.env`, credentials, API keys, JWT signing secrets — all gitignored. CI runs `gitleaks` to catch accidents. If you accidentally commit a secret: rotate it immediately, then `git filter-repo` to scrub history.
- **Never log PHI.** Patient names, IDs, KRA PINs, NSSF/SHIF numbers must not appear in `logger.info`/`error` calls. Log object IDs only.
- **Multi-tenant filter mandatory.** Every query must filter by `facility_id` from JWT. PRs that introduce a missing filter will be rejected.
- **Audit trail mandatory.** Every state-changing finance / payroll operation writes to `audit_logs` (or domain-specific equivalent like `finance_audit_logs`).
- **Encrypt sensitive PII at rest.** Bank accounts, ID numbers — see `services/api-gateway/SECURITY-TODO.md`.

---

## Testing

### Unit tests are required for

- New service-layer functions
- New AI prompts (test guardrails block clinical/PHI)
- New posting rules (verify DR=CR for representative scenarios)
- New tax / PAYE / NSSF / SHIF / Housing Levy logic (worked examples)
- Bug fixes (regression test for the bug)

### Integration tests are required for

- New API endpoints (use `tests/conftest.py` patterns)
- New DB migrations (verify upgrade + downgrade)

### Manual testing is required for

- New frontend pages (smoke-test in light + dark mode, check offline behaviour)
- New AI flows (verify guardrails fire on clinical / PHI prompts)
- Permission-gated endpoints (verify 403 for unauthorised role)

---

## Local Setup

### Prerequisites

```
Node.js 20+, pnpm 9+
Python 3.12+, pip
Go 1.22+
Docker + Docker Compose
```

### First-time setup

```bash
git clone https://github.com/JGitaka123/Aifya.git
cd Aifya

cp .env.example .env       # then fill in secrets

make dev                   # boots Postgres, Redis, Kafka, Keycloak, MinIO
pnpm install               # frontend deps

cd services/api-gateway
pip install -r requirements.txt
alembic upgrade head
python scripts/seed_demo.py    # optional — for demo data

uvicorn app.main:app --reload --port 8000 &

cd ../../apps/web
pnpm dev
```

Open http://localhost:3000 to see the app.

### Running tests locally

```bash
make test                  # all tests
cd apps/web && pnpm test   # frontend only
cd services/api-gateway && pytest -v   # backend only
cd services/billing-service && go test ./...   # Go service only
```

---

## A Note for the Team

**`pipiblack/Aifya-main` is no longer a canonical repo.** Going forward, all work happens in [`JGitaka123/Aifya`](https://github.com/JGitaka123/Aifya). If you have local changes in a clone of `pipiblack/Aifya-main`, please:

1. Push them to a feature branch on `JGitaka123/Aifya` (you have collaborator access)
2. Open a PR against `develop`
3. Then **delete** `pipiblack/Aifya-main` to avoid future confusion

This keeps history clean and reviews centralised.

---

## Questions

Open a [discussion](https://github.com/JGitaka123/Aifya/discussions) or ping the maintainer in your usual channel.

For Aifya project context, see `CLAUDE.md` in the repo root.
