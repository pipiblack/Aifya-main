from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    agents, analytics, appointments, billing, cds, clinical_trials, communications, dental,
    dhis2, emergency, encounters, federated, fhir, finance, help_bot, hr, imaging, insurance, inventory,
    ipd, laboratory, licensing, mch, mpesa, patients, payroll, performance, pharmacy, radiology,
    referral, reports, theatre,
)
from app.middleware.license_guard import LicenseGuardMiddleware

# Disable OpenAPI/Swagger docs in production to avoid exposing API surface
_is_dev: bool = settings.debug
_docs_url: str | None = "/api/docs" if _is_dev else None
_redoc_url: str | None = "/api/redoc" if _is_dev else None
_openapi_url: str | None = "/api/openapi.json" if _is_dev else None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown hooks."""
    # Startup: pre-fetch Keycloak JWKS
    from app.auth.keycloak import get_keycloak_public_keys

    try:
        await get_keycloak_public_keys()
    except Exception:
        pass  # Keycloak may not be running in dev — will retry on first request
    yield


app = FastAPI(
    title="Aifya API",
    description="AI-Native Hospital Management System API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# License enforcement middleware — checks module access on every request
app.add_middleware(LicenseGuardMiddleware)

# Routes
app.include_router(patients.router, prefix="/api/v1/patients", tags=["patients"])
app.include_router(cds.router, prefix="/api/v1/cds", tags=["cds"])
app.include_router(encounters.router, prefix="/api/v1/encounters", tags=["encounters"])
app.include_router(pharmacy.router, prefix="/api/v1/pharmacy", tags=["pharmacy"])
app.include_router(laboratory.router, prefix="/api/v1/laboratory", tags=["laboratory"])
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(finance.router, prefix="/api/v1/finance", tags=["finance"])
app.include_router(ipd.router, prefix="/api/v1/ipd", tags=["ipd"])
app.include_router(radiology.router, prefix="/api/v1/radiology", tags=["radiology"])
app.include_router(mch.router, prefix="/api/v1/mch", tags=["mch"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(hr.router, prefix="/api/v1/hr", tags=["hr"])
app.include_router(payroll.router, prefix="/api/v1/payroll", tags=["payroll"])
app.include_router(emergency.router, prefix="/api/v1/emergency", tags=["emergency"])
app.include_router(inventory.router, prefix="/api/v1/inventory", tags=["inventory"])
app.include_router(theatre.router, prefix="/api/v1/theatre", tags=["theatre"])
app.include_router(referral.router, prefix="/api/v1/referrals", tags=["referrals"])
app.include_router(insurance.router, prefix="/api/v1/insurance", tags=["insurance"])
app.include_router(dental.router, prefix="/api/v1/dental", tags=["dental"])
app.include_router(licensing.router, prefix="/api/v1/licensing", tags=["licensing"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(communications.router, prefix="/api/v1/communications", tags=["communications"])
app.include_router(fhir.router, prefix="/api/v1/fhir", tags=["fhir"])
app.include_router(dhis2.router, prefix="/api/v1/dhis2", tags=["dhis2"])
app.include_router(mpesa.router, prefix="/api/v1/mpesa", tags=["mpesa"])
app.include_router(imaging.router, prefix="/api/v1/imaging", tags=["imaging"])
app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
app.include_router(clinical_trials.router, prefix="/api/v1/trials", tags=["clinical-trials"])
app.include_router(federated.router, prefix="/api/v1/federated", tags=["federated"])
app.include_router(performance.router, prefix="/api/v1/performance", tags=["performance"])
app.include_router(help_bot.router, prefix="/api/v1/help", tags=["help-bot"])


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "service": "aifya-api-gateway"}
