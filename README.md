# Aifya

> **Akili kwa Afya** — Intelligence for Health

AI-native Hospital Management Information System built for Kenyan hospitals. 49 clinical and administrative modules, offline-first architecture, self-hosted LLMs, and full Kenya compliance (SHA, DPA, DHIS2, KRA eTIMS).

---

## Highlights

- **49 modules** covering the full hospital workflow — OPD, IPD, pharmacy, lab, radiology, billing, MCH, emergency, dental, theatre, HR, inventory, insurance, clinical trials, and more
- **3 flagship AI modules**: ScribeAI (ambient clinical documentation), ClaimFlow (SHA claims automation), Clinical Trials (AI screening + REDCap sync)
- **Offline-first**: core workflows (registration, vitals, prescriptions) work fully offline via IndexedDB + background sync
- **Bilingual**: English and Swahili (next-intl), switchable per user
- **Self-hosted AI**: DeepSeek-R1 671B, Qwen 3.5 72B, Distill-32B, MedGemma 27B on A100 80GB GPUs via vLLM — no patient data leaves the facility
- **Event-sourced clinical data**: immutable audit trail, 20-year retention, FHIR R4 export
- **Multi-tenant**: facility-scoped via JWT + PostgreSQL Row-Level Security

## Architecture

```
                        ┌─────────────────────┐
                        │    Next.js 15 PWA    │
                        │  React 19 + shadcn   │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │               │
             ┌──────▼──────┐ ┌────▼─────┐  ┌─────▼──────┐
             │ API Gateway │ │ Billing  │  │   Sync     │
             │  FastAPI    │ │ Go / Gin │  │ Go / Gin   │
             └──────┬──────┘ └──────────┘  └────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        │           │           │              │
   ┌────▼───┐  ┌───▼────┐ ┌───▼───┐   ┌─────▼─────┐
   │ Postgres│  │ Redis  │ │ Kafka │   │ AI Service│
   │ 16 +   │  │  7     │ │  3.7  │   │  vLLM     │
   │Timescale│  └────────┘ └───────┘   │  Whisper  │
   └────────┘                          │  Qdrant   │
                                       └───────────┘
```

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript 5.5+, Tailwind 4, shadcn/ui, TanStack Query 5, TanStack Table 8, Zustand 5, React Hook Form + Zod, next-intl, Recharts, Socket.IO, Workbox PWA |
| **Backend** | Python 3.12+, FastAPI 0.115+, SQLAlchemy 2 (async), Pydantic 2, Celery 5 |
| **Go Services** | Go 1.22+, Gin (billing-service, sync-service) |
| **Data** | PostgreSQL 16 + TimescaleDB, Redis 7, Qdrant, MinIO, Kafka 3.7+ |
| **AI** | vLLM 0.6+ (4 model endpoints), faster-whisper, LlamaIndex, BGE-M3, MedGemma 27B |
| **Auth** | Keycloak 25 (OIDC/RBAC) |
| **Infra** | Docker Compose, K3s, Traefik, Prometheus, Grafana, Loki, Tempo, Vault |
| **Integrations** | SHA e-Claims, DHIS2, M-Pesa Daraja, REDCap v14+, FHIR R4, HL7/ASTM, KRA eTIMS |

## Modules

### Clinical
| Module | Description |
|---|---|
| OPD | Outpatient queue, encounters, triage |
| IPD | Admissions, wards, beds, nursing notes, discharge |
| Emergency | Triage (ESI/KTAS), rapid assessment, disposition |
| Pharmacy | Dispensing queue, inventory, drug interactions |
| Laboratory | Orders, specimen tracking, results, critical alerts |
| Radiology | Imaging orders, PACS viewer, reports |
| MCH | Antenatal, delivery, child health, immunizations |
| Dental | Dental charts, treatment plans, procedures |
| Theatre | Surgical scheduling, operative notes |
| Clinical Trials | Protocol management, AI screening, REDCap sync, SAE reporting |

### Administrative
| Module | Description |
|---|---|
| Patients | Registration, search, demographics, FHIR export |
| Billing | Invoicing, M-Pesa, insurance claims, waivers |
| Insurance | SHA integration, pre-auth, claim tracking |
| Appointments | Scheduling, slots, check-in, no-show analytics |
| HR | Staff profiles, shifts, leave, attendance |
| Inventory | Items, suppliers, purchase orders, stock alerts |
| Communications | SMS/email, templates, bulk messaging |
| Analytics | AI predictions (readmission, stockout, revenue), dashboards |
| Reports | DHIS2 auto-reporting, MOH reports, custom queries |
| Referrals | Inter-facility referrals, status tracking |
| Knowledge Base | Clinical protocols, facility SOPs |
| Settings | Facility config, branding, user management |

### AI-Powered
| Module | Description |
|---|---|
| ScribeAI | Ambient documentation — records consultations, generates SOAP notes |
| ClaimFlow | Automates SHA claim submission, tracks rejections, suggests fixes |
| CDS | Clinical Decision Support — drug interactions, vitals alerts, lab flags |
| AI Screening | Scans encounters against active trial criteria, ranks candidates |

## Project Structure

```
aifya/
├── apps/
│   └── web/                    # Next.js 15 frontend
│       └── src/
│           ├── app/[locale]/   # 25+ page routes
│           ├── components/     # shadcn/ui + custom components
│           ├── hooks/          # TanStack Query hooks (offline-first)
│           └── lib/            # API client, offline store, utils
├── services/
│   ├── api-gateway/            # FastAPI backend (30 routers)
│   │   ├── app/routers/        # All API endpoints
│   │   ├── app/models/         # SQLAlchemy models
│   │   ├── app/schemas/        # Pydantic schemas
│   │   └── tests/              # pytest suite (13 test files)
│   ├── ai-service/             # LLM orchestration (vLLM, Whisper)
│   ├── billing-service/        # Go billing microservice
│   └── sync-service/           # Go offline sync service
├── packages/
│   └── shared/                 # Shared TypeScript types + utils
├── infrastructure/
│   └── keycloak/               # Realm config, roles
├── docs/                       # Architecture specs
├── docker-compose.yml          # Full stack (15+ services)
├── Makefile                    # Dev commands
└── pnpm-workspace.yaml         # Monorepo config
```

## Getting Started

### Prerequisites

- **Node.js 20+** and **pnpm 9+**
- **Python 3.12+** with pip
- **Go 1.22+**
- **Docker** and **Docker Compose**
- **PostgreSQL 16** (or use Docker)

### Quick Start

```bash
# 1. Clone
git clone https://github.com/JGitaka123/Aifya.git
cd Aifya

# 2. Environment
cp .env.example .env
# Edit .env with your database credentials and API keys

# 3. Start infrastructure (Postgres, Redis, Kafka, Keycloak, MinIO)
make dev

# 4. Install frontend dependencies
pnpm install

# 5. Run database migrations
cd services/api-gateway
pip install -r requirements.txt
alembic upgrade head
cd ../..

# 6. Start the API gateway
cd services/api-gateway
uvicorn app.main:app --reload --port 8000 &
cd ../..

# 7. Start the frontend
cd apps/web
pnpm dev
# Open http://localhost:3000
```

### AI Services (Optional)

Requires NVIDIA A100 80GB GPUs with vLLM installed:

```bash
# DeepSeek-R1 671B (complex reasoning) — port 8001
# Qwen 3.5 72B (general tasks) — port 8002
# Distill-32B (fast, simple tasks) — port 8003
# MedGemma 27B (clinical/medical tasks) — port 8004
# Whisper (audio transcription) — port 8005
# See services/ai-service/ for configuration
```

**MedGemma 27B** is Google's medically fine-tuned Gemma 3 model (87.7% on MedQA). It handles:
- Clinical documentation (ScribeAI SOAP notes)
- Trial screening and eligibility matching
- Medical imaging analysis (chest X-ray, retinal scans)
- Drug interaction checks and CDS alerts
- Bilingual patient education (English/Swahili)

VRAM: ~54 GB BF16 or ~27 GB INT8 on a single A100 80GB. 128K context window.

## Development

```bash
# Run all tests
make test

# Individual test suites
cd apps/web && pnpm test           # Vitest (54+ frontend tests)
cd services/api-gateway && python -m pytest -v   # pytest (200+ backend tests)
cd services/billing-service && go test ./...     # Go tests

# Linting
make lint                          # ESLint + Ruff + golangci-lint

# Type checking
make typecheck                     # tsc --noEmit + mypy

# Database
make db-migrate                    # Run migrations
make db-revision msg="description" # Create new migration
```

## API

The API gateway exposes **30 router modules** at `http://localhost:8000/api/v1/`:

| Area | Endpoints |
|---|---|
| `/patients` | Registration, search, demographics |
| `/encounters` | OPD/IPD encounters, vitals, diagnoses |
| `/pharmacy` | Dispensing, inventory, drug interactions |
| `/billing` | Invoices, payments, waivers |
| `/laboratory` | Orders, results, critical alerts |
| `/radiology` | Imaging orders, reports |
| `/appointments` | Scheduling, check-in |
| `/ipd` | Admissions, wards, beds, discharge |
| `/emergency` | Triage, queue, disposition |
| `/mch` | Antenatal, delivery, immunizations |
| `/hr` | Staff, shifts, leave, attendance |
| `/inventory` | Items, suppliers, purchase orders |
| `/clinical-trials` | Protocols, screening, visits, SAE |
| `/fhir` | FHIR R4 resources (Patient, Encounter, Observation, etc.) |
| `/analytics` | AI predictions, dashboards |
| `/cds` | Clinical decision support evaluations |
| `/licensing` | License validation, module access |
| `/communications` | Messaging, templates |

Interactive API docs at `http://localhost:8000/docs` (Swagger UI).

## Kenya Compliance

- **SHA**: Automated e-Claims submission via ClaimFlow
- **DHIS2**: Auto-reporting of MOH indicators
- **KRA eTIMS**: Tax invoice integration for billing
- **M-Pesa**: Daraja API for patient payments
- **DPA/ODPC**: Consent management, data protection audit trail
- **Digital Health Act**: Compliant record retention (20 years)

## Clinical Safety

- AI **never** auto-commits to patient records — clinician sign-off required
- Drug interaction checks **block** on critical interactions before prescription save
- Critical lab values trigger **immediate** alerts
- Serious Adverse Events (SAE) reportable within **24 hours**
- All data access logged to **immutable event store**

## Contributing

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for branch strategy, PR rules, commit conventions, and the security/clinical-safety bar every change must clear.

In short:
- Feature work → `feat/<scope>` branch → PR to `develop`
- Bug fixes → `fix/<scope>` branch → PR to `develop`
- Hotfixes → `hotfix/<scope>` branch → PR to `main` AND `develop`
- Releases → PR `develop` → `main` (tagged with version)
- All PRs must pass CI (lint + typecheck + tests + secrets scan)

## License

Proprietary. All rights reserved.

---

Built with care for Kenyan healthcare.
