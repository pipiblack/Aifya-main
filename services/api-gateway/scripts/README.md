# Aifya — Operational Scripts

Standalone scripts for demo seeding, ops tasks, and one-shot maintenance.

## `seed_demo.py` — Comprehensive Demo Seed

Loads everything needed to demo Aifya end-to-end against a clean database.
The script is **idempotent**: re-running it does not create duplicates.

### Run

Before first run, run database migrations:

```bash
cd services/api-gateway
alembic upgrade head
```

Then seed:

```bash
python scripts/seed_demo.py
```

To soft-delete all demo data (sets `is_deleted=True` on every row tied to
the demo facility, plus `is_active=False` on the facility itself):

```bash
python scripts/seed_demo.py --reset
```

### What it Creates

| Section                       | Count   | Notes                                                   |
| ----------------------------- | ------- | ------------------------------------------------------- |
| Facility                      | 1       | "Aifya Demo Hospital" (`AIFYA-DEMO`, MFL `99999`)       |
| Departments                   | 8       | OPD, IPD, Pharmacy, Lab, Radiology, MCH, ER, Admin      |
| Staff (HMIS users)            | 10      | Doctors, nurses, pharmacist, lab tech, cashier, HR      |
| Patients                      | 15      | Mix of ages 1mo to 75y, SHA / private / cash, pregnant  |
| Pharmacy items                | 15      | Common Kenyan hospital drugs with stock + KES pricing   |
| Insurance schemes             | 1       | SHA                                                     |
| Chart of Accounts             | 27      | From `app.services.finance.seed_data`                   |
| Posting rules                 | ~12     | invoice_cash, invoice_insurance, payroll_run, etc.      |
| Accounting periods            | 26      | 12 monthly + 1 fiscal year for current and prior year   |
| Invoices                      | 25      | Mix of cash (60%) and insurance (40%) + GL postings     |
| Payments                      | ~15     | Insurance settlements (full + partial)                  |
| Expense postings              | 8       | Rent, utilities, supplies, etc.                         |
| Statutory rates               | 11+     | PAYE bands, NSSF tiers, SHIF, HL, personal relief       |
| Leave types                   | 7       | Annual, sick, maternity, paternity, etc.                |
| Employees (payroll)           | 12      | Full KRA PIN, NSSF, SHIF, bank, salary structure        |
| Payroll runs                  | 1       | Previous month, approved + GL-posted                    |
| Leave requests                | 5       | Approved / pending / rejected mix                       |
| Fixed assets                  | 4       | Ultrasound, X-ray, ICU monitor, hospital beds           |
| Budget lines                  | 10      | Departmental budgets for current month                  |
| Recurring templates           | 3       | Rent, payroll, insurance premium                        |
| M-Pesa STK Push samples       | 5       | Mix of success, pending, failed                         |

### Idempotency

The script uses **deterministic UUIDs** generated from
`uuid5(DEMO_NAMESPACE, label)` for every entity it creates. Re-running
yields identical IDs, so unique-index inserts collide cleanly with
"already exists" check-then-skip logic.

For entities without a natural unique key (invoices, payments, expenses,
payroll runs), the script skips work entirely once any rows are
detected for the demo facility.

### Login Credentials

The script seeds the **database only** — it does **NOT** create users in
Keycloak. After seeding, a Keycloak admin must create matching users in
the `aifya` realm so demo logins work:

| Email                  | Password         | Role                  |
| ---------------------- | ---------------- | --------------------- |
| admin@aifya.co.ke      | DemoAdmin2026!   | Admin / Finance       |
| doctor@aifya.co.ke     | DemoDoctor2026!  | Doctor                |
| nurse@aifya.co.ke      | DemoNurse2026!   | Nurse                 |
| pharmacy@aifya.co.ke   | DemoPharm2026!   | Pharmacist            |
| lab@aifya.co.ke        | DemoLab2026!     | Lab Tech              |
| cashier@aifya.co.ke    | DemoCash2026!    | Cashier / Billing     |
| hr@aifya.co.ke         | DemoHR2026!      | HR Admin              |
| reception@aifya.co.ke  | DemoRec2026!     | Receptionist          |

Each `Staff` row carries a deterministic `keycloak_user_id`. After
creating the Keycloak users, either link Keycloak's user IDs to the
existing `Staff.keycloak_user_id` values, or update the `Staff` rows to
match the IDs Keycloak assigns.

### Engines Exercised (not raw SQL)

The script intentionally uses the production code paths to exercise
the real engines:

- `app.services.finance.posting_engine.post_transaction()` for every
  invoice / payment / expense → posts a balanced double-entry journal,
  enforces period locks, idempotency keys.
- `app.services.payroll.engine.run_monthly_payroll()` for the demo run
  → loads PAYE bands, NSSF tiers, SHIF / HL rates, computes per-employee
  pay slips.
- `app.services.payroll.gl_integration.post_payroll_to_gl()` for the
  payroll → finance bridge (compound journal).

### Caveats

- The payroll-to-GL bridge in `gl_integration.py` references account
  codes (`5001`, `1002`, `2034`, ...) that differ from the codes seeded
  by `seed_facility_finance` (`5000`, `1020`, `2200`, ...). The bridge
  fails gracefully with a `WARN` log if the codes don't match — this is
  expected for the demo and does not break the seed.
- The seed runs in a single committed DB session at the end — partial
  failures roll back cleanly.
