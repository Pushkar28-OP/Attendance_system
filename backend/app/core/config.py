from functools import lru_cache
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Aurelix Smart Attendance"
    environment: str = "development"
    mongodb_uri: str = Field(default="mongodb://localhost:27017", validation_alias="MONGODB_URI")
    database_name: str = Field(default="aurelix_attendance", validation_alias="DATABASE_NAME")
    jwt_secret: str = Field(default="change-me-in-env", validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=480, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    face_match_threshold: float = Field(default=0.45, validation_alias="FACE_MATCH_THRESHOLD")
    office_latitude: float | None = Field(default=None, validation_alias="OFFICE_LATITUDE")
    office_longitude: float | None = Field(default=None, validation_alias="OFFICE_LONGITUDE")
    office_radius_meters: float = Field(default=150, validation_alias="OFFICE_RADIUS_METERS")
    cors_origins: list[str] = Field(default=["http://localhost:5173"], validation_alias="CORS_ORIGINS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
