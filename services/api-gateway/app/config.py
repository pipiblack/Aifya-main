from pydantic import model_validator
from pydantic_settings import BaseSettings

# Sentinel values that must be overridden via environment / .env
_INSECURE_DEFAULTS = {
    "change_me_use_openssl_rand_hex_32",
    "change_me_in_production",
    "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://aifya_user:change_me_in_production@localhost:5432/aifya"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    # Auth (Keycloak)
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "aifya"
    keycloak_client_id: str = "aifya-api"
    secret_key: str = "change_me_use_openssl_rand_hex_32"

    # AI Service
    ai_service_url: str = "http://localhost:8010"
    vllm_medgemma_url: str = "http://localhost:8004/v1"
    vllm_qwen_72b_url: str = "http://localhost:8002/v1"

    # M-Pesa Daraja
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_passkey: str = ""
    mpesa_callback_url: str = "https://api.aifyahealth.co.ke/api/v1/mpesa/callback"
    mpesa_environment: str = "sandbox"

    # SHA (Social Health Authority)
    sha_api_url: str = ""
    sha_api_key: str = ""

    # Africa's Talking Bulk SMS
    at_username: str = ""
    at_api_key: str = ""
    at_sender_id: str = "AIFYA"
    at_sandbox: bool = False

    # App
    debug: bool = False
    facility_timezone: str = "Africa/Nairobi"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def mpesa_base_url(self) -> str:
        """
        Derive Daraja API base URL from environment.

        @returns Production URL if mpesa_environment is "production", else sandbox
        """
        if self.mpesa_environment == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @model_validator(mode="after")
    def _reject_insecure_defaults(self) -> "Settings":
        """Crash on startup if critical secrets still use placeholder defaults."""
        if not self.debug:
            if self.secret_key in _INSECURE_DEFAULTS:
                raise ValueError(
                    "SECRET_KEY must be set to a secure random value. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            if self.database_url in _INSECURE_DEFAULTS:
                raise ValueError(
                    "DATABASE_URL must be set to a real connection string. "
                    "Do not use the placeholder default in production."
                )
        return self


settings = Settings()
