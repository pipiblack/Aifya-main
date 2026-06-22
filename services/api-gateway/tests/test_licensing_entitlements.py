"""
Regression tests for tier/module reconciliation.

Professional is the local pre-deploy tier and should not leave application
modules locked in the sidebar or backend route guards.
"""

from app.middleware.license_guard import ROUTE_MODULE_MAP
from app.schemas.licensing import TIER_ENTITLEMENTS
from app.services.licensing_service import _effective_tier


def test_professional_includes_every_route_guard_module() -> None:
    professional_modules = set(
        TIER_ENTITLEMENTS["professional"]["enabled_modules"]
    )
    route_modules = set(ROUTE_MODULE_MAP.values())

    assert route_modules <= professional_modules


def test_professional_includes_every_router_dependency_module() -> None:
    professional_modules = set(
        TIER_ENTITLEMENTS["professional"]["enabled_modules"]
    )
    required_modules = {
        "analytics",
        "appointments",
        "billing",
        "clinical_trials",
        "communications",
        "dental",
        "dhis2_sync",
        "emergency",
        "encounters",
        "fhir",
        "finance",
        "hr",
        "insurance",
        "inventory",
        "ipd",
        "laboratory",
        "mch",
        "patients",
        "pharmacy",
        "radiology",
        "referrals",
        "reports",
        "theatre",
    }

    assert required_modules <= professional_modules


def test_professional_includes_all_ai_features() -> None:
    professional = TIER_ENTITLEMENTS["professional"]

    assert professional["feature_flags"]["ai_features"] is True
    assert "scribe_ai" in professional["enabled_modules"]
    assert "claimflow_ai" in professional["enabled_modules"]
    assert "cds" in professional["enabled_modules"]
    assert "agents" in professional["enabled_modules"]


def test_local_default_tier_floor_is_professional(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.licensing_service.settings.default_license_tier",
        "professional",
    )

    assert _effective_tier("community") == "professional"
