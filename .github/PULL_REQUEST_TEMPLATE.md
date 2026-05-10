<!--
  Thanks for contributing to Aifya. Please fill this in.
  Delete sections that don't apply.
-->

## Summary

<!-- 1-3 sentences explaining WHY this change is needed and what it does. Not what files changed — git already shows that. -->

Closes #

## Changes

<!-- Bulleted list of what shipped. Group by area if multiple modules touched. -->

-

## Screenshots / Demo

<!-- For UI changes: paste before/after screenshots or a short clip.
     For backend changes: paste a curl example or test output. -->

## Test Plan

<!-- How did you verify this works? -->

- [ ] Unit tests added / updated
- [ ] Integration tests added / updated
- [ ] Manually tested in browser (light + dark mode)
- [ ] Manually tested offline (if affects offline-first flow)
- [ ] Manually tested in Swahili (if user-facing strings)

## Checklist

### Required (CI also enforces these)

- [ ] CI is green on this PR
- [ ] No `any` in TypeScript
- [ ] Full Python type hints + no bare `except:`
- [ ] No secrets, credentials, or PHI committed
- [ ] Commit messages follow `type(scope): description` format

### Required for clinical / safety-impacting changes

- [ ] Clinical safety implications considered and documented above
- [ ] Failure modes tested
- [ ] AI changes preserve clinician sign-off requirement
- [ ] Drug-interaction / critical-value alert logic preserved

### Required for finance / payroll / billing changes

- [ ] Double-entry DR = CR validation preserved
- [ ] Period locks honoured
- [ ] Idempotency keys handled correctly
- [ ] Audit log entries written for state changes
- [ ] Statutory rates kept as configuration (not hardcoded)

### Required for migration changes

- [ ] Migration upgrade + downgrade both tested
- [ ] No `op.drop_column()` (use `is_deprecated` flag instead)
- [ ] FK dependency order maintained

### Required for security-impacting changes

- [ ] Multi-tenant `facility_id` filter on every new query
- [ ] Role-based access enforced (`require_roles`)
- [ ] PII not exposed in list endpoints
- [ ] No new attack surface (XSS, SQLi, SSRF) introduced

## Deployment Notes

<!-- Anything ops needs to know? Migrations to run, env vars to set, feature flags to flip, downtime expected? -->

## Reviewer Notes

<!-- Anything specific the reviewer should focus on? Open questions you want feedback on? -->
