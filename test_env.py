import os
os.environ["SECRET_KEY"] = "b2c5545a90ad01fecceb3c3756eb41ed089455359dd4b2a8f82855140b991cd6"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://aifya_user:production.aifyahealth@aifya_postgres:5432/aifya"
os.environ["REDIS_URL"] = "redis://aifya_redis:6379/0"

from app.config import settings
print("Successfully loaded settings:", settings.model_dump())
